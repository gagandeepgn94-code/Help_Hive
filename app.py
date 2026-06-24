# pyrefly: ignore [missing-import]
from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
from flask_socketio import SocketIO
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
import os
import boto3
from boto3.dynamodb.conditions import Key
import uuid
import json
import bcrypt
import time
from ai_engine import predict_emergency

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

# ================= AWS CLIENTS =================

dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

sns_client = boto3.client(
    "sns",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

volunteers_table = dynamodb.Table("Volunteers")
requests_table = dynamodb.Table("Requests")

app = Flask(__name__)
app.secret_key = SECRET_KEY
socketio = SocketIO(app)

# ================= CONFIGURATION =================

app.permanent_session_lifetime = timedelta(days=7)

# Adaptive radius configuration (in KM) — expands by priority
RADIUS_CONFIG = {
    'High':   [10, 20, 30, 40, 50],
    'Medium': [10, 20, 30],
    'Low':    [10, 20]
}

# Categories that can cross-match when searching for volunteers
CATEGORY_CROSS_MATCH = {
    'Doctor': ['Nurse'],
    'Nurse': ['Doctor'],
}

# ================= HELPER FUNCTIONS =================


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula.
    Returns distance in KM or None if coordinates are invalid."""

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


def get_volunteer_by_name(name):
    """Query volunteer by name using GSI. Returns dict or None.
    Falls back to scan if GSI is not yet created."""

    try:
        # Use GSI for O(1) lookup instead of full table scan
        response = volunteers_table.query(
            IndexName='name-index',
            KeyConditionExpression=Key('name').eq(name)
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception:
        # Fallback to scan if GSI doesn't exist yet
        response = volunteers_table.scan()
        for v in response['Items']:
            if v['name'] == name:
                return v
        return None


def get_volunteers_by_category(category):
    """Query volunteers by category using GSI. Returns list.
    Falls back to scan if GSI is not yet created."""

    try:
        response = volunteers_table.query(
            IndexName='category-index',
            KeyConditionExpression=Key('category').eq(category)
        )
        return response.get('Items', [])
    except Exception:
        response = volunteers_table.scan()
        return [v for v in response['Items'] if v.get('category') == category]


def get_requests_by_category(category):
    """Query requests by category using GSI. Returns list.
    Falls back to scan if GSI is not yet created."""

    try:
        response = requests_table.query(
            IndexName='category-status-index',
            KeyConditionExpression=Key('category').eq(category)
        )
        return response.get('Items', [])
    except Exception:
        response = requests_table.scan()
        return [r for r in response['Items'] if r.get('category') == category]


def get_all_requests_paginated():
    """Get all requests with pagination support for large datasets."""

    items = []
    response = requests_table.scan()
    items.extend(response['Items'])

    while 'LastEvaluatedKey' in response:
        response = requests_table.scan(
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response['Items'])

    return items


def get_all_volunteers_paginated():
    """Get all volunteers with pagination support for large datasets."""

    items = []
    response = volunteers_table.scan()
    items.extend(response['Items'])

    while 'LastEvaluatedKey' in response:
        response = volunteers_table.scan(
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response['Items'])

    return items


def update_request_status(request_id, new_status):
    """Update the status of a help request. Reused by accept/complete routes."""

    requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": new_status}
    )


def is_category_match(request_category, volunteer_category):
    """Check if a request category matches the volunteer's expertise.
    Supports cross-matching (e.g., Doctor can see Nurse requests)."""

    if request_category == volunteer_category:
        return True

    cross = CATEGORY_CROSS_MATCH.get(volunteer_category, [])
    return request_category in cross


def find_nearby_requests(volunteer, all_requests, volunteer_category):
    """Find requests within adaptive radius based on priority level.
    Expands radius tier-by-tier (10 → 20 → 30 → 40 → 50 KM) and
    uses the smallest tier that contains each request.

    High priority: expands up to 50 KM
    Medium priority: expands up to 30 KM
    Low priority: expands up to 20 KM
    """

    v_lat = volunteer.get('latitude', '')
    v_lon = volunteer.get('longitude', '')

    matched_requests = []

    for req in all_requests:
        request_category = req.get('category', '')

        # Skip if category doesn't match
        if not is_category_match(request_category, volunteer_category):
            continue

        request_lat = req.get('latitude', '')
        request_lon = req.get('longitude', '')

        distance = calculate_distance(v_lat, v_lon, request_lat, request_lon)

        if distance is None:
            continue

        # Use AI recommended radius if stored on the request, otherwise fall back to priority tiers
        ai_radius = req.get('ai_recommended_radius')

        if ai_radius:
            # AI-powered radius: use single radius from AI prediction
            try:
                ai_radius = int(ai_radius)
            except (ValueError, TypeError):
                ai_radius = None

        if ai_radius and distance <= ai_radius:
            req['distance'] = distance
            req['search_radius'] = ai_radius
            matched_requests.append(req)
        elif not ai_radius:
            # Fallback: adaptive expansion using priority tiers
            radii = RADIUS_CONFIG.get(req.get('priority', 'Low'), [10])
            for radius in radii:
                if distance <= radius:
                    req['distance'] = distance
                    req['search_radius'] = radius
                    matched_requests.append(req)
                    break

    return matched_requests


def validate_required_fields(form, fields):
    """Validate that all required form fields are present and non-empty.
    Returns list of error messages (empty if valid)."""

    errors = []
    for field in fields:
        if not form.get(field, '').strip():
            errors.append(f"'{field}' is required")
    return errors


def require_volunteer_session(f):
    """Decorator to enforce that a volunteer is logged in.
    Redirects to login page if no session exists."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if 'volunteer' not in session:
            return redirect('/volunteer_login')
        return f(*args, **kwargs)
    return decorated


# ================= SNS NOTIFICATIONS =================


def send_sms(phone_number, category, priority, address):
    """Send an SMS notification via AWS SNS to a volunteer.
    
    Args:
        phone_number: Volunteer's phone number (any common Indian format)
        category: Emergency category (e.g. 'Doctor', 'Fire Rescue')
        priority: Priority level ('High', 'Medium', 'Low')
        address: Location/address of the emergency
    """

    # ---- Normalize phone number to E.164 (+91XXXXXXXXXX) ----
    raw = phone_number.strip().replace(' ', '').replace('-', '')

    if raw.startswith('+'):
        # Already in E.164 (e.g. +919876543210) — use as-is
        e164 = raw
    elif raw.startswith('91') and len(raw) == 12:
        # Country code without plus (e.g. 919876543210)
        e164 = '+' + raw
    elif raw.startswith('0') and len(raw) == 11:
        # Local format with leading 0 (e.g. 09876543210)
        e164 = '+91' + raw[1:]
    elif len(raw) == 10 and raw.isdigit():
        # 10-digit Indian mobile number (e.g. 9876543210)
        e164 = '+91' + raw
    else:
        print(f"[SNS] Invalid phone format '{phone_number}' — cannot normalize to E.164, skipping SMS")
        return False

    print(f"[SNS] Sending SMS to {e164} (original: '{phone_number}') | {category} | {priority}")

    message = (
        f"HelpHive Emergency Alert\n\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n"
        f"Location: {address}\n\n"
        f"Immediate assistance is required.\n\n"
        f"Please open HelpHive to respond."
    )

    try:
        response = sns_client.publish(
            PhoneNumber=e164,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        print(f"[SNS] SUCCESS SMS delivered to {e164} - MessageId: {response.get('MessageId')}")
        return True
    except Exception as e:
        print(f"[SNS] FAILED SMS failed for {e164}: {type(e).__name__}: {e}")
        return False


def notify_volunteer(volunteer, request_data):
    """Notify a single volunteer via SMS."""

    phone = volunteer.get('phone', '').strip()
    name = volunteer.get('name', 'Unknown')

    if not phone:
        print(f"[SNS] Could not notify {name} - no phone number")
        return False

    return send_sms(
        phone,
        request_data.get('category', 'Emergency'),
        request_data.get('priority', 'Unknown'),
        request_data.get('address', 'Nearby')
    )


def notify_nearby_volunteers(request_data, ai_radius=None):
    """Send SMS alerts to nearby volunteers matching the request.
    Uses AI recommended radius if provided, otherwise falls back to
    adaptive radius expansion by priority tiers."""

    category = request_data.get('category', '')
    priority = request_data.get('priority', 'Low')

    # Get matching volunteers using GSI
    volunteers = get_volunteers_by_category(category)

    # Also get cross-matched volunteers
    cross_categories = CATEGORY_CROSS_MATCH.get(category, [])
    for cross_cat in cross_categories:
        volunteers.extend(get_volunteers_by_category(cross_cat))

    # Pre-compute distances once (avoid recalculating per tier)
    volunteer_distances = []
    for volunteer in volunteers:
        distance = calculate_distance(
            request_data.get('latitude', ''),
            request_data.get('longitude', ''),
            volunteer.get('latitude', ''),
            volunteer.get('longitude', '')
        )
        if distance is not None:
            volunteer_distances.append((volunteer, distance))

    # If AI provided a radius, use it as a single-tier search
    if ai_radius:
        notified_count = 0
        for volunteer, distance in volunteer_distances:
            if distance <= ai_radius:
                if notify_volunteer(volunteer, request_data):
                    notified_count += 1

        print(f"[SNS] AI radius={ai_radius} KM - notified {notified_count} volunteers for {category}")
        return notified_count

    # Fallback: adaptive expansion by priority tiers
    radii = RADIUS_CONFIG.get(priority, [10])
    notified_count = 0
    previous_radius = 0

    for radius in radii:
        # Find volunteers in this new ring (between previous_radius and radius)
        tier_volunteers = [
            v for v, d in volunteer_distances
            if d <= radius and d > previous_radius
        ]

        for volunteer in tier_volunteers:
            if notify_volunteer(volunteer, request_data):
                notified_count += 1

        if notified_count > 0:
            print(f"[SNS] Found {notified_count} volunteers within {radius} KM - stopping expansion")
            break

        previous_radius = radius
        print(f"[SNS] No volunteers within {radius} KM for {category} - expanding radius")

    if notified_count == 0:
        print(f"[SNS] No volunteers found for {category} request at any radius")

    return notified_count


# ================= ROUTES =================


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

    # Validate required fields
    required = ['name', 'category', 'help', 'priority', 'latitude', 'longitude']
    errors = validate_required_fields(request.form, required)

    if errors:
        return f"Missing fields: {', '.join(errors)}", 400

    name = request.form['name'].strip()
    category = request.form['category'].strip()
    help_text = request.form['help'].strip()
    priority = request.form['priority'].strip()
    latitude = request.form['latitude'].strip()
    longitude = request.form['longitude'].strip()
    address = request.form.get('address', '').strip()

    request_time = datetime.now().strftime("%d-%m-%Y %H:%M")

    request_data = {
        "request_id": str(uuid.uuid4()),
        "name": name,
        "category": category,
        "help": help_text,
        "priority": priority,
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "status": "Pending",
        "time": request_time
    }

    # ---- AI Prediction (single call) ----
    ai_start = time.time()
    try:
        # Estimate nearby volunteers for AI context
        nearby_volunteers = len(get_volunteers_by_category(category))

        ai_result = predict_emergency(
            category=category,
            description=help_text,
            request_time=request_time,
            nearby_volunteers=nearby_volunteers
        )

        ai_latency = round(time.time() - ai_start, 2)
        print(f"[AI] Prediction completed in {ai_latency}s - {ai_result.get('priority')}, confidence={ai_result.get('confidence')}")

    except Exception as e:
        ai_latency = round(time.time() - ai_start, 2)
        print(f"[AI] Prediction failed after {ai_latency}s (non-blocking): {e}")
        ai_result = {
            "priority": "Medium",
            "severity_score": 5.0,
            "confidence": 0.0,
            "recommended_radius": 10,
            "notify_immediately": False,
            "reason": "AI unavailable"
        }

    # Store AI outputs in the request (never overwrite user priority)
    request_data["ai_priority"] = ai_result.get("priority", "Medium")
    request_data["ai_severity_score"] = str(ai_result.get("severity_score", 5.0))
    request_data["ai_confidence"] = str(ai_result.get("confidence", 0.0))
    request_data["ai_recommended_radius"] = str(ai_result.get("recommended_radius", 10))
    request_data["ai_notify_immediately"] = ai_result.get("notify_immediately", False)
    request_data["ai_reason"] = ai_result.get("reason", "AI unavailable")

    requests_table.put_item(Item=request_data)

    # Emit real-time Socket.IO notification
    socketio.emit(
        'new_request',
        {
            'category': category,
            'priority': priority,
            'ai_priority': request_data['ai_priority'],
            'address': address
        }
    )

    # ---- Send SMS using AI radius ----
    ai_radius = ai_result.get('recommended_radius', None)
    notify_now = ai_result.get('notify_immediately', False)

    try:
        if notify_now:
            print(f"[AI] notify_immediately=True - sending SMS immediately")
            notify_nearby_volunteers(request_data, ai_radius=ai_radius)
        else:
            notify_nearby_volunteers(request_data, ai_radius=ai_radius)
    except Exception as e:
        print(f"[SNS] Notification error (non-blocking): {e}")

    return redirect('/request-help')

# ================= VOLUNTEER REGISTER =================

@app.route('/register_volunteer', methods=['POST'])
def register_volunteer():

    # Validate required fields (password now required)
    required = ['name', 'phone', 'category', 'password']
    errors = validate_required_fields(request.form, required)

    if errors:
        return f"Missing fields: {', '.join(errors)}", 400

    name = request.form['name'].strip()
    password = request.form['password'].strip()
    phone = request.form['phone'].strip()
    email = request.form.get('email', '').strip()
    category = request.form['category'].strip()
    availability = request.form.get('availability', 'Available').strip()
    latitude = request.form.get('latitude', '').strip()
    longitude = request.form.get('longitude', '').strip()

    # Check if volunteer already exists
    existing = get_volunteer_by_name(name)
    if existing:
        return "A volunteer with this name already exists. Please login instead.", 400

    # Hash password with bcrypt
    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    volunteers_table.put_item(
        Item={
            "volunteer_id": str(uuid.uuid4()),
            "name": name,
            "password": hashed_password,
            "phone": phone,
            "email": email,
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

    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    remember = request.form.get('remember')

    if not name or not password:
        return "Name and password are required", 400

    # Use GSI query instead of full table scan
    volunteer = get_volunteer_by_name(name)

    if not volunteer:
        return "Volunteer Not Registered"

    # Verify password with bcrypt
    stored_password = volunteer.get('password', '')

    if not stored_password:
        # Legacy volunteer without password — deny login
        return "Account requires password reset. Please contact admin.", 403

    if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
        return "Invalid password", 401

    session['volunteer'] = name

    if remember:
        session.permanent = True
    else:
        session.permanent = False

    return redirect('/volunteer')

# ================= VOLUNTEER DASHBOARD =================

@app.route('/volunteer')
@require_volunteer_session
def volunteer():

    volunteer_name = session['volunteer']

    # Get volunteer using GSI query (not scan)
    current_volunteer = get_volunteer_by_name(volunteer_name)

    if not current_volunteer:
        return "Volunteer not found"

    volunteer_category = current_volunteer['category']

    # Get requests matching volunteer's category using GSI
    category_requests = get_requests_by_category(volunteer_category)

    # Also get cross-matched category requests
    cross_categories = CATEGORY_CROSS_MATCH.get(volunteer_category, [])
    for cross_cat in cross_categories:
        category_requests.extend(get_requests_by_category(cross_cat))

    # Filter by adaptive radius
    filtered_requests = find_nearby_requests(
        current_volunteer, category_requests, volunteer_category
    )

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

    # Serialize all data for JS
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

    volunteer_lat = current_volunteer.get('latitude', '')
    volunteer_lon = current_volunteer.get('longitude', '')

    # Convert to float for safe JSON rendering in the template
    # DynamoDB may return Decimal type, or the value may be an empty string
    try:
        volunteer_lat = float(volunteer_lat) if volunteer_lat not in ('', None) else 0
    except (ValueError, TypeError):
        volunteer_lat = 0
    try:
        volunteer_lon = float(volunteer_lon) if volunteer_lon not in ('', None) else 0
    except (ValueError, TypeError):
        volunteer_lon = 0

    return render_template(
        'volunteer.html',
        requests=filtered_requests,
        notification_count=notification_count,
        volunteer_lat=volunteer_lat,
        volunteer_lon=volunteer_lon,
        current_volunteer=current_volunteer,
        status_json=json.dumps(status_counts),
        priority_json=json.dumps(priority_counts),
        category_json=json.dumps(category_counts),
        request_data_json=request_data_json
    )

# ================= ADMIN ANALYTICS DASHBOARD =================

@app.route('/admin/analytics')
def admin_analytics():
    """Global analytics dashboard with cross-volunteer metrics."""

    all_requests = get_all_requests_paginated()
    all_volunteers = get_all_volunteers_paginated()

    # Core metrics
    total_requests = len(all_requests)
    pending = sum(1 for r in all_requests if r.get('status') == 'Pending')
    accepted = sum(1 for r in all_requests if r.get('status') == 'Accepted')
    completed = sum(1 for r in all_requests if r.get('status') == 'Completed')
    active_volunteers = sum(1 for v in all_volunteers if v.get('availability') == 'Available')
    total_volunteers = len(all_volunteers)

    # Response rate
    responded = accepted + completed
    response_rate = round((responded / max(total_requests, 1)) * 100, 1)

    metrics = {
        'total_requests': total_requests,
        'pending': pending,
        'accepted': accepted,
        'completed': completed,
        'active_volunteers': active_volunteers,
        'total_volunteers': total_volunteers,
        'response_rate': response_rate
    }

    # Category distribution for chart
    category_counts = {}
    for r in all_requests:
        cat = r.get('category', 'Other')
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Priority distribution for chart
    priority_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    for r in all_requests:
        p = r.get('priority', 'Low')
        if p in priority_counts:
            priority_counts[p] += 1

    # Status distribution for chart
    status_counts = {'Pending': pending, 'Accepted': accepted, 'Completed': completed}

    # Recent requests (latest 10)
    recent_requests = sorted(
        all_requests,
        key=lambda x: x.get('time', ''),
        reverse=True
    )[:10]

    return render_template(
        'admin_analytics.html',
        metrics=metrics,
        category_json=json.dumps(category_counts),
        priority_json=json.dumps(priority_counts),
        status_json=json.dumps(status_counts),
        recent_requests=recent_requests
    )

# ================= REQUEST ACTIONS =================

@app.route('/accept/<request_id>')
@require_volunteer_session
def accept(request_id):
    update_request_status(request_id, "Accepted")
    return redirect('/volunteer')


@app.route('/complete/<request_id>')
@require_volunteer_session
def complete(request_id):
    update_request_status(request_id, "Completed")
    return redirect('/volunteer')


@app.route('/delete/<request_id>')
@require_volunteer_session
def delete(request_id):
    requests_table.delete_item(
        Key={"request_id": request_id}
    )
    return redirect('/volunteer')

# ================= LOGOUT =================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# ================= UTILITY ROUTES =================

@app.route('/reset')
def reset():
    return "Reset not migrated to DynamoDB yet"


@app.route('/test')
def test():
    return "APP IS WORKING"

@app.route("/test-sms")
def test_sms():

    sns = boto3.client(
        "sns",
        region_name=os.getenv("AWS_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    response = sns.publish(
        PhoneNumber="+91YOUR_NUMBER",
        Message="🚨 HelpHive Test SMS\nAWS SNS is working successfully!"
    )

    return response["MessageId"]

# ================= RUN =================

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)