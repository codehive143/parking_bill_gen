from flask import Flask, render_template_string, request, send_file, redirect, url_for, session
from fpdf import FPDF
from datetime import datetime
import io
import json
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Secure random secret key

# Four users with different passwords
USERS = {
    'Arivuselvi': 'arivu123',
    'Venkatesan': 'venkat123', 
    'Dhiyanes': 'dhiya123',
    'Master': 'Master123'  # Note: Capital 'M' in Master
}

# Storage for billed records
BILLED_FILE = '/tmp/billed_records.json'  # Use /tmp for Vercel compatibility

# Exactly 14 parking slots
PARKING_SLOTS = [f"SLOT-{i:02d}" for i in range(1, 15)]

# Year options
YEARS = [str(year) for year in range(2020, 2050)]

def initialize_files():
    """Initialize data files if they don't exist"""
    try:
        if not os.path.exists(BILLED_FILE):
            with open(BILLED_FILE, 'w') as f:
                json.dump([], f, indent=2)
        return True
    except Exception as e:
        print(f"Error initializing files: {e}")
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
        with open(BILLED_FILE, 'w') as f:
            json.dump([], f, indent=2)
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
    """Decorator to require master user - FIXED: using correct username"""
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or session.get('username') != 'Master':  # Changed to 'Master'
            return "Access denied. Master privileges required.", 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
@login_required
def home():
    return redirect(url_for('billing'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in USERS and USERS[username] == password:
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
    
    # Group by slot and month
    slot_wise = {}
    month_wise = {}
    
    for record in records:
        # Slot-wise grouping
        slot = record['slot_number']
        if slot not in slot_wise:
            slot_wise[slot] = []
        slot_wise[slot].append(record)
        
        # Month-wise grouping
        month_key = f"{record['month']} {record['year']}"
        if month_key not in month_wise:
            month_wise[month_key] = []
        month_wise[month_key].append(record)
    
    # FIXED: Check for 'Master' instead of 'master'
    is_master = session.get('username') == 'Master'
    return render_template_string(BILLED_HTML, 
                                slot_wise=slot_wise,
                                month_wise=month_wise,
                                username=session.get('username'),
                                is_master=is_master,
                                total_records=len(records))

@app.route('/reset_billing', methods=['POST'])
@login_required
@master_required
def reset_billing():
    """Reset all billing data - only accessible by master user"""
    if reset_billed_records():
        return redirect(url_for('billed'))
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
        
        # Header - Normal size
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(200, 10, txt="VENGATESAN CAR PARKING", ln=1, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt="Tittagudi | Contact: 9791365506", ln=1, align="C")
        pdf.ln(10)
        
        # Title - Normal size
        pdf.set_font("Arial", style="B", size=18)
        pdf.cell(200, 15, txt="MONTHLY PARKING BILL", ln=1, align="C")
        pdf.ln(5)
        
        # Bill Details - Normal size
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
        
        # Amount Section - Normal size
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(200, 10, txt="AMOUNT DETAILS", ln=1)
        pdf.set_font("Arial", size=11)
        
        pdf.cell(120, 10, txt="Monthly Parking Charges:", ln=0)
        pdf.cell(70, 10, txt=f"Rs. 1000.00", ln=1)
        
        pdf.ln(8)
        
        # Total Amount - Normal size
        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(120, 12, txt="TOTAL AMOUNT:", ln=0)
        pdf.cell(70, 12, txt=f"Rs. 1000.00", ln=1)
        
        pdf.ln(15)
        
        # FOOTER SECTION - SMALLER FONT SIZES
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 4, txt="-" * 50, ln=1, align="C")
        pdf.set_font("Arial", style="B", size=10)
        pdf.cell(200, 6, txt="CODE HIVE", ln=1, align="C")
        pdf.set_font("Arial", style="I", size=8)
        pdf.cell(200, 5, txt="LEARN AND LEAD", ln=1, align="C")
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 4, txt="-" * 50, ln=1, align="C")
        pdf.ln(2)
        
        # Developer Information - Smaller
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 5, txt="Development Partner", ln=1, align="C")
        pdf.set_font("Arial", size=7)
        pdf.cell(200, 4, txt="Email: codehive143@gmail.com", ln=1, align="C")
        pdf.cell(200, 4, txt="Phone: +91 6374576277", ln=1, align="C")
        pdf.cell(200, 4, txt="Specialized in Web Applications & Automation", ln=1, align="C")
        pdf.ln(3)
        
        # Final Footer - Smallest
        pdf.set_font("Arial", style="I", size=7)
        pdf.cell(200, 4, txt="Thank you for choosing Vengatesan Car Parking!", ln=1, align="C")
        pdf.cell(200, 4, txt="This is a computer-generated bill.", ln=1, align="C")
        pdf.ln(2)
        pdf.set_font("Arial", style="B", size=7)
        pdf.cell(200, 4, txt="Powered by CodeHive - Your Technology Partner", ln=1, align="C")
        
        # FIXED: Generate PDF bytes correctly
        pdf_output = pdf.output(dest='S')  # Returns string for 'S' destination
        
        # Convert to bytes
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode('latin-1')
        else:
            pdf_bytes = bytes(pdf_output)
        
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
        return f"Error generating bill: {str(e)}"

# HTML Templates with updated users and reset button
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Login - Parking Bill Generator</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 400px; 
            margin: 50px auto; 
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
            width: 100%;
        }
        .logo {
            font-size: 48px;
            margin-bottom: 15px;
        }
        h2 {
            color: #333;
            margin-bottom: 20px;
        }
        .form-group { 
            margin: 15px 0; 
            text-align: left;
        }
        label { 
            display: block; 
            margin-bottom: 5px; 
            font-weight: bold;
            color: #333;
        }
        input { 
            width: 100%; 
            padding: 10px; 
            border: 2px solid #ddd; 
            border-radius: 8px;
            font-size: 14px;
            box-sizing: border-box;
        }
        button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            padding: 12px; 
            border: none; 
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            cursor: pointer;
            margin-top: 10px;
        }
        .error {
            color: #ff6b6b;
            margin: 10px 0;
            font-size: 14px;
        }
        .user-list {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            margin-top: 10px;
            text-align: left;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">🅿️</div>
        <h2>Vengatesan Car Parking</h2>
        <p>Please login to continue</p>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <div class="form-group">
                <label>Username:</label>
                <input type="text" name="username" placeholder="Enter username" required>
            </div>
            
            <div class="form-group">
                <label>Password:</label>
                <input type="password" name="password" placeholder="Enter password" required>
            </div>
            
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
'''

BILLING_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Billing - Parking Bill Generator</title>
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
        .nav-item:hover {
            background: #f0f0f0;
        }
        .user-info {
            color: #666;
            font-size: 14px;
        }
        .container {
            max-width: 600px; 
            margin: 20px auto; 
            padding: 20px;
        }
        .main-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #eee;
            padding-bottom: 15px;
        }
        .parking-logo {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #4CAF50, #45a049);
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 24px;
            margin-right: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .header-text h2 {
            margin: 0;
            color: #333;
            font-size: 28px;
        }
        .header-text p {
            margin: 5px 0 0 0;
            color: #666;
            font-size: 14px;
        }
        .form-container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .form-group { 
            margin: 20px 0; 
        }
        label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: bold;
            color: #333;
        }
        input, select { 
            width: 100%; 
            padding: 12px; 
            border: 2px solid #ddd; 
            border-radius: 8px;
            font-size: 16px;
        }
        input:focus, select:focus { 
            outline: none; 
            border-color: #667eea; 
        }
        button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            padding: 15px; 
            border: none; 
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            cursor: pointer;
            margin-top: 10px;
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
            <div class="main-header">
                <div class="parking-logo">P</div>
                <div class="header-text">
                    <h2>Monthly Billing</h2>
                    <p>Generate new parking bills</p>
                </div>
            </div>
            
            <div class="business-info">
                <p><strong>📍 Address:</strong> Tittagudi</p>
                <p><strong>📞 Contact:</strong> 9791365506</p>
                <p><strong>💰 Monthly Rate:</strong> Rs. 1000</p>
            </div>
            
            <form action="/generate" method="POST">
                <div class="form-group">
                    <label>Customer Name:</label>
                    <input type="text" name="name" placeholder="Enter customer full name" required>
                </div>
                
                <div class="form-group">
                    <label>Vehicle Number:</label>
                    <input type="text" name="vehicle_no" placeholder="e.g., TN45AB1234" required>
                </div>
                
                <div class="form-group">
                    <label>Vehicle Type:</label>
                    <select name="vehicle_type" required>
                        <option value="">Select Vehicle Type</option>
                        <option value="car">Car</option>
                        <option value="bike">Bike</option>
                        <option value="truck">Truck</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Parking Slot Number:</label>
                    <select name="slot_number" required>
                        <option value="">Select Parking Slot</option>
                        {% for slot in slots %}
                        <option value="{{ slot }}">{{ slot }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Parking Month:</label>
                    <select name="month" required>
                        <option value="">Select Month</option>
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
                    <label>Year:</label>
                    <select name="year" required>
                        <option value="">Select Year</option>
                        {% for year in years %}
                        <option value="{{ year }}" {% if year == current_year %}selected{% endif %}>{{ year }}</option>
                        {% endfor %}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Payment Mode:</label>
                    <select name="payment_mode" required>
                        <option value="">Select Payment Mode</option>
                        <option value="Online">Online Payment</option>
                        <option value="Cash">Cash</option>
                    </select>
                </div>
                
                <button type="submit">Generate Parking Bill PDF</button>
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
    <title>Billed Records - Parking Bill Generator</title>
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
        .nav-item:hover {
            background: #f0f0f0;
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
        .section {
            margin-bottom: 40px;
        }
        .section-title {
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .slot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
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
        .month-section {
            margin-bottom: 15px;
        }
        .month-header {
            background: #2c3e50;
            color: white;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 10px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background-color 0.3s;
        }
        .month-header:hover {
            background: #34495e;
        }
        .month-content {
            display: none;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
            margin-top: 5px;
        }
        .month-content.show {
            display: block;
        }
        .toggle-icon {
            font-size: 16px;
            transition: transform 0.3s;
        }
        .toggle-icon.rotated {
            transform: rotate(180deg);
        }
        .no-records {
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 20px;
        }
        .records-count {
            background: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 10px;
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
            margin: 10px 0;
        }
        .reset-btn:hover {
            background: #c0392b;
        }
        .master-badge {
            background: #e74c3c;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 10px;
        }
        .stats-info {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
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
                <strong>Slots Used: {{ slot_wise|length }}/14</strong> | 
                <strong>Months Billed: {{ month_wise|length }}</strong>
            </div>
            {% endif %}

            <!-- Slot-wise Section -->
            <div class="section">
                <h2 class="section-title">
                    <span>Slot-wise Billing</span>
                    <span>Total Slots: {{ slot_wise|length }}/14</span>
                </h2>
                {% if slot_wise %}
                <div class="slot-grid">
                    {% for slot, records in slot_wise.items() %}
                    <div class="slot-card">
                        <div class="slot-header">{{ slot }} <span class="records-count">{{ records|length }}</span></div>
                        {% for record in records %}
                        <div class="record-item">
                            <strong>{{ record.name }}</strong><br>
                            Vehicle: {{ record.vehicle_no }} ({{ record.vehicle_type }})<br>
                            Period: {{ record.month }} {{ record.year }}<br>
                            Payment: {{ record.payment_mode }}<br>
                            <small>Billed on: {{ record.bill_date }} by {{ record.created_by }}</small>
                        </div>
                        {% endfor %}
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                <div class="no-records">No billed records found</div>
                {% endif %}
            </div>

            <!-- Month-wise Section -->
            <div class="section">
                <h2 class="section-title">
                    <span>Month-wise Billing (Click to Expand)</span>
                    <span>Total Months: {{ month_wise|length }}</span>
                </h2>
                {% if month_wise %}
                {% for month, records in month_wise.items() %}
                <div class="month-section">
                    <div class="month-header" onclick="toggleMonth('month-{{ loop.index }}')">
                        <span>{{ month }} <span class="records-count">{{ records|length }}</span></span>
                        <span class="toggle-icon">▼</span>
                    </div>
                    <div class="month-content" id="month-{{ loop.index }}">
                        <div class="slot-grid">
                            {% for record in records %}
                            <div class="record-item">
                                <strong>{{ record.name }}</strong><br>
                                Slot: {{ record.slot_number }}<br>
                                Vehicle: {{ record.vehicle_no }} ({{ record.vehicle_type }})<br>
                                Payment: {{ record.payment_mode }}<br>
                                <small>Billed on: {{ record.bill_date }} by {{ record.created_by }}</small>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% endfor %}
                {% else %}
                <div class="no-records">No billed records found</div>
                {% endif %}
            </div>

            <!-- Master Reset Section -->
            {% if is_master %}
            <div class="reset-section">
                <h3>🔧 Master Control Panel</h3>
                <p><strong>Warning:</strong> This will permanently delete all billing records and start fresh.</p>
                <p>Total records to be deleted: <strong>{{ total_records }}</strong></p>
                <form action="/reset_billing" method="POST" onsubmit="return confirmReset()">
                    <button type="submit" class="reset-btn">🚨 RESET ALL BILLING DATA</button>
                </form>
                <small>Only available to Master user</small>
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        function toggleMonth(monthId) {
            const content = document.getElementById(monthId);
            const toggleIcon = content.previousElementSibling.querySelector('.toggle-icon');
            
            content.classList.toggle('show');
            toggleIcon.classList.toggle('rotated');
        }

        function confirmReset() {
            return confirm('🚨 ARE YOU SURE?\n\nThis will permanently delete ALL billing records ({{ total_records }} records).\nThis action cannot be undone!');
        }

        // Optional: Auto-expand first month
        document.addEventListener('DOMContentLoaded', function() {
            const firstMonth = document.querySelector('.month-content');
            if (firstMonth) {
                firstMonth.classList.add('show');
                const firstToggleIcon = firstMonth.previousElementSibling.querySelector('.toggle-icon');
                firstToggleIcon.classList.add('rotated');
            }
        });
    </script>
</body>
</html>
'''

# Initialize files when the app starts
initialize_files()

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
    print("📁 Initializing data files...")
    initialize_files()
    print("✅ System ready!")
    print("👤 Available users:")
    for username, password in USERS.items():
        print(f"   {username} / {password}")
    app.run(debug=True)
