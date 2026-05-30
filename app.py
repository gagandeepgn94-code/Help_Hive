from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret123"

# ================= SESSION =================

app.permanent_session_lifetime = timedelta(days=7)

# ================= TEMP STORAGE =================

volunteers = []
requests_list = []

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

    data = {

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

    requests_list.append(data)

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

    volunteer = {
        "name": name,
        "occupation": occupation,
        "phone": phone,
        "category": category,
        "availability": availability,
        "latitude": latitude,
        "longitude": longitude
    }

    volunteers.append(volunteer)

    session['volunteer'] = name

    return redirect('/volunteer')

    
# ================= VOLUNTEER LOGIN =================

@app.route('/login_volunteer', methods=['POST'])
def login_volunteer():

    name = request.form['name']

    remember = request.form.get('remember')

    for volunteer in volunteers:

        if volunteer['name'] == name:

            session['volunteer'] = name

            if remember:
                session.permanent = True
            else:
                session.permanent = False

            return redirect('/volunteer')

    return "Volunteer Not Registered"

# ================= VOLUNTEER LOGIN PAGE =================

@app.route('/volunteer_login')
def volunteer_login_page():

    if 'volunteer' in session:
        return redirect('/volunteer')

    return render_template('volunteer_login.html')

# ================= VOLUNTEER DASHBOARD =================

@app.route('/volunteer')
def volunteer():

    if 'volunteer' not in session:
        return redirect('/volunteer_login')

    search = request.args.get('search', '')

    if search:

        filtered = [

            r for r in requests_list

            if search.lower() in r['category'].lower()

        ]

    else:

        filtered = requests_list

    return render_template(
        'volunteer.html',
        requests=filtered
    )

# ================= ACCEPT REQUEST =================

@app.route('/accept/<int:index>')
def accept(index):

    requests_list[index]['status'] = "Accepted"

    return redirect('/volunteer')

# ================= COMPLETE REQUEST =================

@app.route('/complete/<int:index>')
def complete(index):

    requests_list[index]['status'] = "Completed"

    return redirect('/volunteer')

# ================= DELETE REQUEST =================

@app.route('/delete/<int:index>')
def delete(index):

    requests_list.pop(index)

    return redirect('/volunteer')

# ================= LOGOUT =================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# ================= RESET =================

@app.route('/reset')
def reset():

    session.clear()

    volunteers.clear()

    requests_list.clear()

    return redirect('/')

@app.route('/test')
def test():
    return "APP IS WORKING"
# ================= RUN =================

if __name__ == '__main__':
    app.run(debug=True)