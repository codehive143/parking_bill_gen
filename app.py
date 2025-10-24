from flask import Flask, render_template_string, request, send_file, redirect, url_for, session
from fpdf import FPDF
from datetime import datetime
import io
import json
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# User storage file
USERS_FILE = '/tmp/users.json'

# Default users
DEFAULT_USERS = {
    'arivuselvi': 'arivu123',
    'venkatesan': 'venkat123', 
    'dhiyanes': 'dhiya123',
    'master': 'master123'
}

# Storage for billed records
BILLED_FILE = '/tmp/billed_records.json'

# Exactly 14 parking slots
PARKING_SLOTS = [f"SLOT-{i:02d}" for i in range(1, 15)]

# Year options
YEARS = [str(year) for year in range(2020, 2031)]

def load_users():
    """Load users from file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return DEFAULT_USERS.copy()

def save_users(users):
    """Save users to file"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except:
        return False

def load_billed_records():
    """Load billed records from file"""
    try:
        if os.path.exists(BILLED_FILE):
            with open(BILLED_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_billed_record(record):
    """Save a new billed record"""
    records = load_billed_records()
    records.append(record)
    try:
        with open(BILLED_FILE, 'w') as f:
            json.dump(records, f, indent=2)
        return True
    except:
        return False

def reset_billed_records():
    """Reset all billed records (only for master user)"""
    try:
        if os.path.exists(BILLED_FILE):
            os.remove(BILLED_FILE)
        return True
    except:
        return False

# Login required decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def master_required(f):
    """Decorator to require master user"""
    def decorated_function(*args, **kwargs):
        users = load_users()
        if 'logged_in' not in session or session.get('username') != 'master' or users.get('master') is None:
            return "Access denied. Master privileges required.", 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
@login_required
def home():
    return redirect(url_for('billing'))

# Login HTML Template
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Login - Parking System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: bold;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            box-sizing: border-box;
        }
        input[type="text"]:focus,
        input[type="password"]:focus {
            border-color: #667eea;
            outline: none;
        }
        .login-btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        .login-btn:hover {
            opacity: 0.9;
        }
        .error {
            color: #e74c3c;
            text-align: center;
            margin-top: 15px;
            padding: 10px;
            background: #ffeaea;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🅿️ Parking System</h1>
            <p>Vengatesan Car Parking</p>
        </div>
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="login-btn">Login</button>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = load_users()
        if username in users and users[username] == password:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('billing'))
        else:
            return render_template_string(LOGIN_HTML, error="Invalid credentials!")
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Billing HTML Template
BILLING_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Billing - Parking System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .navbar {
            background: white;
            padding: 15px 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .nav-brand {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }
        .nav-menu {
            display: flex;
            gap: 20px;
        }
        .nav-item {
            padding: 8px 16px;
            border-radius: 5px;
            text-decoration: none;
            color: #333;
            font-weight: 500;
        }
        .nav-item.active {
            background: #667eea;
            color: white;
        }
        .user-info {
            color: #666;
            font-size: 14px;
        }
        .container {
            max-width: 800px;
            margin: 30px auto;
            padding: 20px;
        }
        .form-container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: bold;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            box-sizing: border-box;
        }
        input:focus, select:focus {
            border-color: #667eea;
            outline: none;
        }
        .submit-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
        }
        .submit-btn:hover {
            opacity: 0.9;
        }
        .welcome-message {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <div class="nav-brand">🅿️ Vengatesan Parking</div>
        <div class="nav-menu">
            <a href="/billing" class="nav-item active">Billing</a>
            <a href="/billed" class="nav-item">Billed</a>
        </div>
        <div class="user-info">
            Welcome, {{ username }} | <a href="/logout" style="color: #667eea;">Logout</a>
        </div>
    </div>

    <div class="container">
        <div class="form-container">
            <div class="welcome-message">
                <h1>Monthly Parking Bill Generator</h1>
                <p>Generate parking bills for monthly customers</p>
            </div>
            
            <form action="/generate" method="POST">
                <div class="form-group">
                    <label for="name">Customer Name:</label>
                    <input type="text" id="name" name="name" required>
                </div>
                
                <div class="form-group">
                    <label for="vehicle_no">Vehicle Number:</label>
                    <input type="text" id="vehicle_no" name="vehicle_no" required>
                </div>
                
                <div class="form-group">
                    <label for="vehicle_type">Vehicle Type:</label>
                    <select id="vehicle_type" name="vehicle_type" required>
                        <option value="bike">Bike</option>
                        <option value="car">Car</option>
                        <option value="auto">Auto</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="slot_number">Parking Slot:</label>
                    <select id="slot_number" name="slot_number" required>
                        {% for slot in slots %}
                        <option value="{{ slot }}">{{ slot }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="month">Month:</label>
                    <select id="month" name="month" required>
                        <option value="January">January</option>
                        <option value="February">February</option>
                        <option value="March">March</option>
                        <option value="April">April</option>
                        <option value="May">May</option>
                        <option value="June">June</option>
                        <option value="July">July</option>
                        <option value="August">August</option>
                        <option value="September">September</option>
                        <option value="October">October</option>
                        <option value="November">November</option>
                        <option value="December">December</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="year">Year:</label>
                    <select id="year" name="year" required>
                        {% for year in years %}
                        <option value="{{ year }}" {% if year == current_year %}selected{% endif %}>{{ year }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="payment_mode">Payment Mode:</label>
                    <select id="payment_mode" name="payment_mode" required>
                        <option value="Cash">Cash</option>
                        <option value="Online">Online</option>
                        <option value="Card">Card</option>
                        <option value="UPI">UPI</option>
                    </select>
                </div>
                
                <button type="submit" class="submit-btn">Generate Bill PDF</button>
            </form>
        </div>
    </div>
</body>
</html>
'''

@app.route('/billing')
@login_required
def billing():
    current_year = datetime.now().year
    return render_template_string(BILLING_HTML, 
                                slots=PARKING_SLOTS, 
                                years=YEARS, 
                                current_year=current_year,
                                username=session.get('username'))

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    try:
        # Get form data
        name = request.form['name']
        vehicle_no = request.form['vehicle_no']
        vehicle_type = request.form['vehicle_type']
        slot_number = request.form['slot_number']
        month = request.form['month']
        year = request.form['year']
        payment_mode = request.form['payment_mode']
        
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(200, 10, txt="VENGATESAN CAR PARKING", ln=1, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt="Tittagudi | Contact: 9791365506", ln=1, align="C")
        pdf.ln(10)
        
        # Title
        pdf.set_font("Arial", style="B", size=18)
        pdf.cell(200, 15, txt="MONTHLY PARKING BILL", ln=1, align="C")
        pdf.ln(5)
        
        # Bill Details
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(200, 10, txt="BILL DETAILS", ln=1)
        pdf.set_font("Arial", size=11)
        
        details = [
            ("Bill Date", datetime.now().strftime("%d-%m-%Y")),
            ("Customer Name", name),
            ("Vehicle Number", vehicle_no),
            ("Vehicle Type", vehicle_type.upper()),
            ("Parking Slot", slot_number),
            ("Parking Period", f"{month} {year}"),
            ("Payment Mode", payment_mode)
        ]
        
        for label, value in details:
            pdf.cell(60, 8, txt=label + ":", ln=0)
            pdf.cell(130, 8, txt=str(value), ln=1)
        
        pdf.ln(10)
        
        # Amount Section
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(200, 10, txt="AMOUNT DETAILS", ln=1)
        pdf.set_font("Arial", size=11)
        
        pdf.cell(120, 10, txt="Monthly Parking Charges:", ln=0)
        pdf.cell(70, 10, txt=f"Rs. 1000.00", ln=1)
        
        pdf.ln(8)
        
        # Total Amount
        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(120, 12, txt="TOTAL AMOUNT:", ln=0)
        pdf.cell(70, 12, txt=f"Rs. 1000.00", ln=1)
        
        pdf.ln(15)
        
        # Footer Section
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 4, txt="-" * 50, ln=1, align="C")
        pdf.set_font("Arial", style="B", size=10)
        pdf.cell(200, 6, txt="CODE HIVE", ln=1, align="C")
        pdf.set_font("Arial", style="I", size=8)
        pdf.cell(200, 5, txt="LEARN AND LEAD", ln=1, align="C")
        
        # Generate PDF bytes - FIXED VERSION
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        
        filename = f"Parking_Bill_{name.replace(' ', '_')}_{month}_{year}.pdf"
        
        # Save billed record
        billed_record = {
            'name': name,
            'vehicle_no': vehicle_no,
            'vehicle_type': vehicle_type,
            'slot_number': slot_number,
            'month': month,
            'year': year,
            'payment_mode': payment_mode,
            'bill_date': datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            'bill_amount': 'Rs. 1000.00',
            'created_by': session.get('username')
        }
        save_billed_record(billed_record)
        
        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return f"Error generating bill: {str(e)}", 500

# Simple Billed Records Page (temporary)
@app.route('/billed')
@login_required
def billed():
    records = load_billed_records()
    return f"""
    <html>
    <head><title>Billed Records</title></head>
    <body>
        <h1>Billed Records</h1>
        <p>Total Records: {len(records)}</p>
        <a href="/billing">Back to Billing</a>
        <br><br>
        {% for record in records %}
        <div style="border:1px solid #ccc; padding:10px; margin:5px;">
            <strong>{record['name']}</strong> - {record['vehicle_no']} - {record['month']} {record['year']}
        </div>
        {% endfor %}
    </body>
    </html>
    """.replace("{% for record in records %}", "").replace("{% endfor %}", "").replace("{{ record['name'] }}", "{}").format(*[f"<div style='border:1px solid #ccc; padding:10px; margin:5px;'><strong>{r['name']}</strong> - {r['vehicle_no']} - {r['month']} {r['year']}</div>" for r in records])

if __name__ == '__main__':
    # Create tmp directory if it doesn't exist
    os.makedirs('/tmp', exist_ok=True)
    
    # Initialize data files if they don't exist
    if not os.path.exists(USERS_FILE):
        save_users(DEFAULT_USERS)
    
    print("Starting Parking Billing System...")
    print("Available users:")
    for username, password in DEFAULT_USERS.items():
        print(f"  {username} / {password}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
