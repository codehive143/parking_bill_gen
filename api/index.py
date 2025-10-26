from flask import Flask, render_template_string, request, send_file, redirect, url_for, session
from fpdf import FPDF
from datetime import datetime
import io
import json
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Four users with different passwords
USERS = {
    'Arivuselvi': 'arivu123',
    'Venkatesan': 'venkat123', 
    'Dhiyanes': 'dhiya123',
    'Master': 'Master123'
}

# In-memory storage for billed records (works on Vercel)
billed_records = []

# Exactly 14 parking slots
PARKING_SLOTS = [f"SLOT-{i:02d}" for i in range(1, 15)]
YEARS = [str(year) for year in range(2020, 2050)]

def load_billed_records():
    """Load billed records from memory"""
    global billed_records
    return billed_records

def save_billed_record(record):
    """Save a new billed record to memory"""
    global billed_records
    billed_records.append(record)
    return True

def reset_billed_records():
    """Reset all billed records (only for Master user)"""
    global billed_records
    billed_records = []
    return True

# Login required decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def master_required(f):
    """Decorator to require Master user"""
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or session.get('username') != 'Master':
            return "Access denied. Master privileges required.", 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def home():
    if 'logged_in' in session:
        return redirect('/billing')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in USERS and USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            return redirect('/billing')
        else:
            return render_template_string(LOGIN_HTML, error="Invalid credentials!")
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/billing')
@login_required
def billing():
    current_year = datetime.now().year
    return render_template_string(BILLING_HTML, 
                                slots=PARKING_SLOTS, 
                                years=YEARS, 
                                current_year=current_year,
                                username=session.get('username'))

@app.route('/billed')
@login_required
def billed():
    records = load_billed_records()
    
    # Group by slot
    slot_wise = {}
    for record in records:
        slot = record['slot_number']
        if slot not in slot_wise:
            slot_wise[slot] = []
        slot_wise[slot].append(record)
    
    is_master = session.get('username') == 'Master'
    return render_template_string(BILLED_HTML, 
                                slot_wise=slot_wise,
                                username=session.get('username'),
                                is_master=is_master,
                                total_records=len(records))

@app.route('/reset_billing', methods=['POST'])
@login_required
@master_required
def reset_billing():
    """Reset all billing data - only accessible by Master user"""
    if reset_billed_records():
        return redirect('/billed')
    else:
        return "Error resetting billing data", 500

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
        
        # Footer
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 4, txt="-" * 50, ln=1, align="C")
        pdf.set_font("Arial", style="B", size=10)
        pdf.cell(200, 6, txt="CODE HIVE", ln=1, align="C")
        pdf.set_font("Arial", style="I", size=8)
        pdf.cell(200, 5, txt="LEARN AND LEAD", ln=1, align="C")
        
        # Generate PDF
        pdf_output = pdf.output(dest='S')
        pdf_bytes = pdf_output.encode('latin-1') if isinstance(pdf_output, str) else pdf_output
        
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

# HTML Templates
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
        .error {
            color: #e74c3c;
            text-align: center;
            margin-top: 15px;
            padding: 10px;
            background: #ffeaea;
            border-radius: 5px;
        }
        .demo-accounts {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            font-size: 12px;
        }
        .user-list {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            margin-top: 10px;
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
                <label>Username:</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password:</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="login-btn">Login</button>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
        </form>
        
        <div class="demo-accounts">
            <h4>Demo Accounts:</h4>
            <div class="user-list">
                <div><strong>Master</strong> / Master123</div>
                <div><strong>Arivuselvi</strong> / arivu123</div>
                <div><strong>Venkatesan</strong> / venkat123</div>
                <div><strong>Dhiyanes</strong> / dhiya123</div>
            </div>
        </div>
    </div>
</body>
</html>
'''

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
        .business-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
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
            
            <div class="business-info">
                <p><strong>📍 Address:</strong> Tittagudi</p>
                <p><strong>📞 Contact:</strong> 9791365506</p>
                <p><strong>💰 Monthly Rate:</strong> Rs. 1000</p>
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

BILLED_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Billed Records - Parking System</title>
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
            max-width: 1200px;
            margin: 20px auto;
            padding: 20px;
        }
        .content-container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .stats-info {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
        }
        .slot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .slot-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            background: #f8f9fa;
        }
        .slot-header {
            background: #667eea;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: -15px -15px 15px -15px;
            text-align: center;
            font-weight: bold;
        }
        .record-item {
            background: white;
            padding: 10px;
            margin: 8px 0;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }
        .reset-section {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
            margin: 30px 0;
            text-align: center;
        }
        .reset-btn {
            background: #e74c3c;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        .master-badge {
            background: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <div class="nav-brand">🅿️ Vengatesan Parking</div>
        <div class="nav-menu">
            <a href="/billing" class="nav-item">Billing</a>
            <a href="/billed" class="nav-item active">Billed</a>
        </div>
        <div class="user-info">
            Welcome, {{ username }} 
            {% if is_master %}<span class="master-badge">MASTER</span>{% endif %}
            | <a href="/logout" style="color: #667eea;">Logout</a>
        </div>
    </div>

    <div class="container">
        <div class="content-container">
            <h1>Billed Records</h1>
            
            {% if total_records > 0 %}
            <div class="stats-info">
                <strong>Total Records: {{ total_records }}</strong> | 
                <strong>Total Revenue: ₹{{ total_records * 1000 }}</strong> | 
                <strong>Slots Used: {{ slot_wise|length }}/14</strong>
            </div>
            {% endif %}

            <div class="slot-grid">
                {% for slot, records in slot_wise.items() %}
                <div class="slot-card">
                    <div class="slot-header">{{ slot }} ({{ records|length }})</div>
                    {% for record in records %}
                    <div class="record-item">
                        <strong>{{ record.name }}</strong><br>
                        Vehicle: {{ record.vehicle_no }}<br>
                        Period: {{ record.month }} {{ record.year }}<br>
                        Payment: {{ record.payment_mode }}<br>
                        <small>By: {{ record.created_by }}</small>
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>

            {% if not slot_wise %}
            <div style="text-align: center; color: #666; padding: 40px;">
                No billed records found
            </div>
            {% endif %}

            {% if is_master %}
            <div class="reset-section">
                <h3>🔧 Master Control</h3>
                <p>Total records: <strong>{{ total_records }}</strong></p>
                <form action="/reset_billing" method="POST" onsubmit="return confirmReset()">
                    <button type="submit" class="reset-btn">🚨 Reset All Data</button>
                </form>
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        function confirmReset() {
            return confirm('🚨 ARE YOU SURE?\\n\\nThis will delete ALL billing records.\\nThis action cannot be undone!');
        }
    </script>
</body>
</html>
'''

# Vercel serverless function handler
def handler(request, context):
    with app.app_context():
        response = app.full_dispatch_request()
        return {
            'statusCode': response.status_code,
            'headers': dict(response.headers),
            'body': response.get_data(as_text=True)
        }

if __name__ == '__main__':
    print("🚀 Parking System Starting...")
    print("✅ System ready!")
    app.run(debug=True)
