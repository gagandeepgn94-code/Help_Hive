# pyrefly: ignore [missing-import]
from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from flask_socketio import SocketIO
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
import os
import boto3
import uuid
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

volunteers_table = dynamodb.Table("Volunteers")
requests_table = dynamodb.Table("Requests")

app = Flask(__name__)
app.secret_key = SECRET_KEY
socketio = SocketIO(app)

def calculate_distance(lat1, lon1, lat2, lon2):

    # Return None if any coordinate is missing/empty
    if not lat1 or not lon1 or not lat2 or not lon2:
        return None

    try:
        R = 6371  # Earth radius in KM

        lat1 = radians(float(lat1))
        lon1 = radians(float(lon1))
        lat2 = radians(float(lat2))
        lon2 = radians(float(lon2))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            sin(dlat / 2) ** 2
            + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        )

        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return round(R * c, 2)
    except (ValueError, TypeError):
        return None

@app.route('/aws-test')
def aws_test():

    try:

        volunteers_table.put_item(
            Item={
                "volunteer_id": str(uuid.uuid4()),
                "name": "AWS Test User",
                "category": "Test"
            }
        )

        return "DynamoDB Connected Successfully ✅"

    except Exception as e:

        return str(e)

# ================= SESSION =================

app.permanent_session_lifetime = timedelta(days=7)


# ================= HOME =================

@app.route('/')
def home():
    return render_template('index.html')

# ================= REQUEST HELP PAGE =================

@app.route('/request-help')
def request_help_page():
    return render_template('request_help.html')

# ================= REQUEST HELP =================

@app.route('/request_help', methods=['POST'])
def request_help():

    name = request.form['name']
    category = request.form['category']
    help_text = request.form['help']
    priority = request.form['priority']
    latitude = request.form['latitude']
    longitude = request.form['longitude']
    address = request.form['address']

    requests_table.put_item(
        Item={
            "request_id": str(uuid.uuid4()),
            "name": name,
            "category": category,
            "help": help_text,
            "priority": priority,
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "status": "Pending",
            "time": datetime.now().strftime("%d-%m-%Y %H:%M")
        }
    )
    socketio.emit(
    'new_request',
    {
        'category': category,
        'priority': priority,
        'address': address
    }
)

    return redirect('/request-help')
# ================= VOLUNTEER REGISTER =================

@app.route('/register_volunteer', methods=['POST'])
def register_volunteer():

    name = request.form['name']
    occupation = request.form['occupation']
    phone = request.form['phone']
    category = request.form['category']
    availability = request.form['availability']
    latitude = request.form['latitude']
    longitude = request.form['longitude']

    volunteers_table.put_item(
        Item={
            "volunteer_id": str(uuid.uuid4()),
            "name": name,
            "occupation": occupation,
            "phone": phone,
            "category": category,
            "availability": availability,
            "latitude": latitude,
            "longitude": longitude
        }
    )

    session['volunteer'] = name

    return redirect('/volunteer')
# ================= VOLUNTEER LOGIN PAGE =================

@app.route('/volunteer_login')
def volunteer_login_page():

    if 'volunteer' in session:
        return redirect('/volunteer')

    return render_template('volunteer_login.html')

@app.route('/login_volunteer', methods=['POST'])
def login_volunteer():

    name = request.form['name']
    remember = request.form.get('remember')

    response = volunteers_table.scan()

    for volunteer in response['Items']:

        if volunteer['name'] == name:

            session['volunteer'] = name

            if remember:
                session.permanent = True
            else:
                session.permanent = False

            return redirect('/volunteer')

    return "Volunteer Not Registered"
# ================= VOLUNTEER DASHBOARD =================

@app.route('/volunteer')
def volunteer():

    if 'volunteer' not in session:
        return redirect('/volunteer_login')

    volunteer_name = session['volunteer']

    # Get volunteer from DynamoDB
    response = volunteers_table.scan()

    current_volunteer = None

    for v in response['Items']:
        if v['name'] == volunteer_name:
            current_volunteer = v
            break

    if not current_volunteer:
        return "Volunteer not found"

    volunteer_category = current_volunteer['category']

    # Get requests from DynamoDB
    response = requests_table.scan()
    all_requests = response['Items']

    filtered_requests = []

    volunteer_lat = current_volunteer.get('latitude', '')
    volunteer_lon = current_volunteer.get('longitude', '')

    for req in all_requests:

        request_category = req.get('category', '')

        request_lat = req.get('latitude', '')
        request_lon = req.get('longitude', '')

        distance = calculate_distance(
            volunteer_lat,
            volunteer_lon,
            request_lat,
            request_lon
        )

        if distance is not None and distance <= 10:

            req['distance'] = distance

            if request_category == volunteer_category:
                filtered_requests.append(req)

            elif volunteer_category == "Doctor" and request_category == "Nurse":
                filtered_requests.append(req)

            elif volunteer_category == "Nurse" and request_category == "Doctor":
                filtered_requests.append(req)

    notification_count = len(filtered_requests)

    # Analytics data for charts
    status_counts = {'Pending': 0, 'Accepted': 0, 'Completed': 0}
    priority_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    category_counts = {}

    for req in filtered_requests:
        s = req.get('status', 'Pending')
        if s in status_counts:
            status_counts[s] += 1

        p = req.get('priority', 'Low')
        if p in priority_counts:
            priority_counts[p] += 1

        cat = req.get('category', 'Other')
        category_counts[cat] = category_counts.get(cat, 0) + 1

    import json

    # Serialize all data for JS to avoid Jinja in script tags
    request_data_json = json.dumps([
        {
            'lat': float(req.get('latitude', 0) or 0),
            'lon': float(req.get('longitude', 0) or 0),
            'category': req.get('category', ''),
            'address': req.get('address', ''),
            'distance': str(req.get('distance', ''))
        }
        for req in filtered_requests
    ])

    return render_template(
        'volunteer.html',
        requests=filtered_requests,
        notification_count=notification_count,
        volunteer_lat=volunteer_lat or 0,
        volunteer_lon=volunteer_lon or 0,
        current_volunteer=current_volunteer,
        status_json=json.dumps(status_counts),
        priority_json=json.dumps(priority_counts),
        category_json=json.dumps(category_counts),
        request_data_json=request_data_json
    )
# ================= LOGOUT =================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# ================= RESET =================

@app.route('/reset')
def reset():
    return "Reset not migrated to DynamoDB yet"

    

@app.route('/test')
def test():
    return "APP IS WORKING"


@app.route('/accept/<request_id>')
def accept(request_id):

    requests_table.update_item(
        Key={
            "request_id": request_id
        },
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={
            "#s": "status"
        },
        ExpressionAttributeValues={
            ":status": "Accepted"
        }
    )

    return redirect('/volunteer')


@app.route('/complete/<request_id>')
def complete(request_id):

    requests_table.update_item(
        Key={
            "request_id": request_id
        },
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={
            "#s": "status"
        },
        ExpressionAttributeValues={
            ":status": "Completed"
        }
    )

    return redirect('/volunteer')


    
@app.route('/delete/<request_id>')
def delete(request_id):

   requests_table.delete_item(
    Key={
        "request_id": request_id
    }
)
   return redirect('/volunteer')

# ================= RUN =================

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)