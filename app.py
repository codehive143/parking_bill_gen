from flask import Flask, render_template_string, request, send_file, redirect, url_for, session
from fpdf import FPDF
from datetime import datetime
import io
import json
import os
import secrets
import csv

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# User storage file
USERS_FILE = '/tmp/users.json'
BILLED_FILE = '/tmp/billed_records.json'
SYSTEM_SETTINGS_FILE = '/tmp/system_settings.json'

# Default users
DEFAULT_USERS = {
    'arivuselvi': 'arivu123',
    'venkatesan': 'venkat123', 
    'dhiyanes': 'dhiya123',
    'master': 'master123'
}

# Default system settings
DEFAULT_SETTINGS = {
    'business_name': 'VENGATESAN CAR PARKING',
    'business_address': 'Tittagudi',
    'business_contact': '9791365506',
    'monthly_rate': 1000,
    'developer_info': 'CODE HIVE - LEARN AND LEAD',
    'developer_contact': 'codehive143@gmail.com',
    'developer_phone': '+91 6374576277'
}

PARKING_SLOTS = [f"SLOT-{i:02d}" for i in range(1, 15)]
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

def load_system_settings():
    """Load system settings from file"""
    try:
        if os.path.exists(SYSTEM_SETTINGS_FILE):
            with open(SYSTEM_SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return DEFAULT_SETTINGS.copy()

def save_system_settings(settings):
    """Save system settings to file"""
    try:
        with open(SYSTEM_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
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

def get_system_stats():
    """Get comprehensive system statistics"""
    records = load_billed_records()
    users = load_users()
    settings = load_system_settings()
    
    # Calculate monthly revenue
    monthly_revenue = {}
    yearly_revenue = {}
    
    for record in records:
        month_key = f"{record['month']} {record['year']}"
        year_key = record['year']
        
        if month_key not in monthly_revenue:
            monthly_revenue[month_key] = 0
        if year_key not in yearly_revenue:
            yearly_revenue[year_key] = 0
            
        monthly_revenue[month_key] += settings['monthly_rate']
        yearly_revenue[year_key] += settings['monthly_rate']
    
    return {
        'total_records': len(records),
        'total_users': len(users),
        'total_revenue': len(records) * settings['monthly_rate'],
        'monthly_revenue': monthly_revenue,
        'yearly_revenue': yearly_revenue,
        'active_slots': len(set(record['slot_number'] for record in records)),
        'billing_months': len(monthly_revenue),
        'billing_years': len(yearly_revenue)
    }

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

@app.route('/billing')
@login_required
def billing():
    current_year = datetime.now().year
    settings = load_system_settings()
    return render_template_string(BILLING_HTML, 
                                slots=PARKING_SLOTS, 
                                years=YEARS, 
                                current_year=current_year,
                                username=session.get('username'),
                                settings=settings)

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
    
    is_master = session.get('username') == 'master'
    stats = get_system_stats()
    
    return render_template_string(BILLED_HTML, 
                                slot_wise=slot_wise,
                                month_wise=month_wise,
                                username=session.get('username'),
                                is_master=is_master,
                                stats=stats)

# Enhanced Master Control Routes

@app.route('/master_control')
@login_required
@master_required
def master_control():
    """Master Control Panel Dashboard"""
    users = load_users()
    settings = load_system_settings()
    stats = get_system_stats()
    
    return render_template_string(MASTER_CONTROL_HTML,
                                users=users,
                                settings=settings,
                                stats=stats,
                                username=session.get('username'))

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
@master_required
def manage_users():
    """User Management - Add, Edit, Delete Users"""
    users = load_users()
    message = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_user':
            new_username = request.form.get('new_username')
            new_password = request.form.get('new_password')
            
            if new_username and new_password:
                if new_username in users:
                    message = {'type': 'error', 'text': f'User "{new_username}" already exists!'}
                else:
                    users[new_username] = new_password
                    if save_users(users):
                        message = {'type': 'success', 'text': f'User "{new_username}" added successfully!'}
                    else:
                        message = {'type': 'error', 'text': 'Error saving users!'}
        
        elif action == 'change_password':
            username = request.form.get('username')
            new_password = request.form.get('new_password')
            
            if username in users and new_password:
                users[username] = new_password
                if save_users(users):
                    message = {'type': 'success', 'text': f'Password for "{username}" changed successfully!'}
                else:
                    message = {'type': 'error', 'text': 'Error saving users!'}
        
        elif action == 'delete_user':
            username = request.form.get('username')
            
            if username in users and username != 'master':  # Prevent deleting master
                del users[username]
                if save_users(users):
                    message = {'type': 'success', 'text': f'User "{username}" deleted successfully!'}
                else:
                    message = {'type': 'error', 'text': 'Error saving users!'}
            elif username == 'master':
                message = {'type': 'error', 'text': 'Cannot delete master user!'}
    
    return render_template_string(USER_MANAGEMENT_HTML,
                                users=users,
                                username=session.get('username'),
                                message=message)

@app.route('/system_settings', methods=['GET', 'POST'])
@login_required
@master_required
def system_settings():
    """System Configuration Settings"""
    settings = load_system_settings()
    message = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_business_info':
            settings['business_name'] = request.form.get('business_name', settings['business_name'])
            settings['business_address'] = request.form.get('business_address', settings['business_address'])
            settings['business_contact'] = request.form.get('business_contact', settings['business_contact'])
            settings['monthly_rate'] = int(request.form.get('monthly_rate', settings['monthly_rate']))
            
            if save_system_settings(settings):
                message = {'type': 'success', 'text': 'Business information updated successfully!'}
            else:
                message = {'type': 'error', 'text': 'Error saving settings!'}
        
        elif action == 'update_developer_info':
            settings['developer_info'] = request.form.get('developer_info', settings['developer_info'])
            settings['developer_contact'] = request.form.get('developer_contact', settings['developer_contact'])
            settings['developer_phone'] = request.form.get('developer_phone', settings['developer_phone'])
            
            if save_system_settings(settings):
                message = {'type': 'success', 'text': 'Developer information updated successfully!'}
            else:
                message = {'type': 'error', 'text': 'Error saving settings!'}
    
    return render_template_string(SYSTEM_SETTINGS_HTML,
                                settings=settings,
                                username=session.get('username'),
                                message=message)

@app.route('/system_backup', methods=['GET', 'POST'])
@login_required
@master_required
def system_backup():
    """System Backup and Data Management"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'export_data':
            # Export all data as JSON
            export_data = {
                'users': load_users(),
                'billed_records': load_billed_records(),
                'system_settings': load_system_settings(),
                'export_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'exported_by': session.get('username')
            }
            
            return json.dumps(export_data, indent=2), 200, {
                'Content-Type': 'application/json',
                'Content-Disposition': 'attachment; filename=parking_system_backup.json'
            }
        
        elif action == 'export_csv':
            # Export billed records as CSV
            records = load_billed_records()
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Name', 'Vehicle Number', 'Vehicle Type', 'Slot', 'Month', 'Year', 
                           'Payment Mode', 'Bill Date', 'Amount', 'Created By'])
            
            # Write data
            for record in records:
                writer.writerow([
                    record['name'],
                    record['vehicle_no'],
                    record['vehicle_type'],
                    record['slot_number'],
                    record['month'],
                    record['year'],
                    record['payment_mode'],
                    record['bill_date'],
                    record['bill_amount'],
                    record['created_by']
                ])
            
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=parking_records.csv'
            }
    
    stats = get_system_stats()
    return render_template_string(SYSTEM_BACKUP_HTML,
                                username=session.get('username'),
                                stats=stats)

@app.route('/system_reports')
@login_required
@master_required
def system_reports():
    """Advanced System Reports"""
    stats = get_system_stats()
    records = load_billed_records()
    settings = load_system_settings()
    
    # Generate detailed reports
    monthly_report = {}
    user_activity = {}
    
    for record in records:
        # Monthly report
        month_key = f"{record['month']} {record['year']}"
        if month_key not in monthly_report:
            monthly_report[month_key] = {
                'total_bills': 0,
                'total_revenue': 0,
                'slots_used': set(),
                'created_by': {}
            }
        
        monthly_report[month_key]['total_bills'] += 1
        monthly_report[month_key]['total_revenue'] += settings['monthly_rate']
        monthly_report[month_key]['slots_used'].add(record['slot_number'])
        
        # User activity
        creator = record['created_by']
        if creator not in user_activity:
            user_activity[creator] = 0
        user_activity[creator] += 1
    
    # Convert sets to counts
    for month in monthly_report:
        monthly_report[month]['unique_slots'] = len(monthly_report[month]['slots_used'])
    
    return render_template_string(SYSTEM_REPORTS_HTML,
                                stats=stats,
                                monthly_report=monthly_report,
                                user_activity=user_activity,
                                username=session.get('username'))

@app.route('/reset_billing', methods=['POST'])
@login_required
@master_required
def reset_billing():
    """Reset all billing data - only accessible by master user"""
    if reset_billed_records():
        return redirect(url_for('master_control'))
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
        
        settings = load_system_settings()
        
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        
        # Header - Normal size
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(200, 10, txt=settings['business_name'], ln=1, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt=f"{settings['business_address']} | Contact: {settings['business_contact']}", ln=1, align="C")
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
        pdf.cell(70, 10, txt=f"Rs. {settings['monthly_rate']}.00", ln=1)
        
        pdf.ln(8)
        
        # Total Amount - Normal size
        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(120, 12, txt="TOTAL AMOUNT:", ln=0)
        pdf.cell(70, 12, txt=f"Rs. {settings['monthly_rate']}.00", ln=1)
        
        pdf.ln(15)
        
        # FOOTER SECTION - SMALLER FONT SIZES
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 4, txt="-" * 50, ln=1, align="C")
        pdf.set_font("Arial", style="B", size=10)
        pdf.cell(200, 6, txt=settings['developer_info'], ln=1, align="C")
        pdf.set_font("Arial", style="I", size=8)
        pdf.cell(200, 5, txt="LEARN AND LEAD", ln=1, align="C")
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 4, txt="-" * 50, ln=1, align="C")
        pdf.ln(2)
        
        # Developer Information - Smaller
        pdf.set_font("Arial", style="B", size=8)
        pdf.cell(200, 5, txt="Development Partner", ln=1, align="C")
        pdf.set_font("Arial", size=7)
        pdf.cell(200, 4, txt=f"Email: {settings['developer_contact']}", ln=1, align="C")
        pdf.cell(200, 4, txt=f"Phone: {settings['developer_phone']}", ln=1, align="C")
        pdf.cell(200, 4, txt="Specialized in Web Applications & Automation", ln=1, align="C")
        pdf.ln(3)
        
        # Final Footer - Smallest
        pdf.set_font("Arial", style="I", size=7)
        pdf.cell(200, 4, txt=f"Thank you for choosing {settings['business_name']}!", ln=1, align="C")
        pdf.cell(200, 4, txt="This is a computer-generated bill.", ln=1, align="C")
        pdf.ln(2)
        pdf.set_font("Arial", style="B", size=7)
        pdf.cell(200, 4, txt="Powered by CodeHive - Your Technology Partner", ln=1, align="C")
        
        # Generate PDF bytes correctly
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
            'bill_amount': f"Rs. {settings['monthly_rate']}.00",
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

# HTML Templates for Enhanced Master Controls

MASTER_CONTROL_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Master Control - Parking System</title>
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
            max-width: 1400px;
            margin: 20px auto;
            padding: 20px;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .dashboard-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
        }
        .dashboard-card h3 {
            margin-top: 0;
            color: #333;
            font-size: 16px;
        }
        .stat-number {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        .control-panel {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }
        .control-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s;
        }
        .control-card:hover {
            transform: translateY(-5px);
        }
        .control-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .control-card p {
            color: #666;
            margin-bottom: 20px;
        }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            transition: opacity 0.3s;
        }
        .btn:hover {
            opacity: 0.9;
        }
        .btn.danger {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        }
        .btn.success {
            background: linear-gradient(135deg, #27ae60 0%, #219a52 100%);
        }
        .master-badge {
            background: #e74c3c;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
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
            <a href="/billed" class="nav-item">Billed</a>
            <a href="/master_control" class="nav-item active">Master Control</a>
        </div>
        <div class="user-info">
            Welcome, {{ username }} <span class="master-badge">MASTER</span>
            | <a href="/logout" style="color: #667eea;">Logout</a>
        </div>
    </div>

    <div class="container">
        <h1 style="color: white; text-align: center; margin-bottom: 30px;">🎛️ Master Control Panel</h1>
        
        <!-- Statistics Dashboard -->
        <div class="dashboard">
            <div class="dashboard-card">
                <h3>Total Bills Generated</h3>
                <div class="stat-number">{{ stats.total_records }}</div>
                <p>All Time</p>
            </div>
            <div class="dashboard-card">
                <h3>Total Revenue</h3>
                <div class="stat-number">₹{{ stats.total_revenue }}</div>
                <p>All Time</p>
            </div>
            <div class="dashboard-card">
                <h3>Active Users</h3>
                <div class="stat-number">{{ stats.total_users }}</div>
                <p>System Users</p>
            </div>
            <div class="dashboard-card">
                <h3>Active Slots</h3>
                <div class="stat-number">{{ stats.active_slots }}/14</div>
                <p>Parking Utilization</p>
            </div>
        </div>

        <!-- Control Panel -->
        <div class="control-panel">
            <div class="control-card">
                <h3>👥 User Management</h3>
                <p>Add, edit, or remove system users</p>
                <a href="/manage_users" class="btn">Manage Users</a>
            </div>
            
            <div class="control-card">
                <h3>⚙️ System Settings</h3>
                <p>Configure business and system settings</p>
                <a href="/system_settings" class="btn">System Settings</a>
            </div>
            
            <div class="control-card">
                <h3>📊 System Reports</h3>
                <p>View detailed analytics and reports</p>
                <a href="/system_reports" class="btn">View Reports</a>
            </div>
            
            <div class="control-card">
                <h3>💾 Backup & Export</h3>
                <p>Export data in JSON or CSV format</p>
                <a href="/system_backup" class="btn success">Data Backup</a>
            </div>
            
            <div class="control-card">
                <h3>🚨 Data Reset</h3>
                <p>Clear all billing records (Danger Zone)</p>
                <form action="/reset_billing" method="POST" onsubmit="return confirmReset()" style="display: inline;">
                    <button type="submit" class="btn danger">Reset All Data</button>
                </form>
            </div>
            
            <div class="control-card">
                <h3>📈 Revenue Analytics</h3>
                <p>Monthly and yearly revenue analysis</p>
                <a href="/system_reports" class="btn">View Analytics</a>
            </div>
        </div>
    </div>

    <script>
        function confirmReset() {
            return confirm('🚨 ARE YOU SURE?\n\nThis will permanently delete ALL billing records ({{ stats.total_records }} records).\nThis action cannot be undone!');
        }
    </script>
</body>
</html>
'''

USER_MANAGEMENT_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>User Management - Parking System</title>
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
            max-width: 1000px;
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
        }
        .form-group {
            margin-bottom: 20px;
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
            box-sizing: border-box;
        }
        .btn {
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin-right: 10px;
        }
        .btn.danger {
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        }
        .users-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .user-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .user-card.master {
            border-left-color: #e74c3c;
            background: #ffeaa7;
        }
        .message {
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .message.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .message.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
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
            <a href="/billed" class="nav-item">Billed</a>
            <a href="/master_control" class="nav-item">Master Control</a>
            <a href="/manage_users" class="nav-item active">User Management</a>
        </div>
        <div class="user-info">
            Welcome, {{ username }} <span class="master-badge">MASTER</span>
            | <a href="/logout" style="color: #667eea;">Logout</a>
        </div>
    </div>

    <div class="container">
        <div class="content-container">
            <h1>👥 User Management</h1>
            
            {% if message %}
            <div class="message {{ message.type }}">{{ message.text }}</div>
            {% endif %}

            <!-- Add User Section -->
            <div class="section">
                <h2 class="section-title">Add New User</h2>
                <form method="POST">
                    <input type="hidden" name="action" value="add_user">
                    <div class="form-group">
                        <label>New Username:</label>
                        <input type="text" name="new_username" required>
                    </div>
                    <div class="form-group">
                        <label>New Password:</label>
                        <input type="password" name="new_password" required>
                    </div>
                    <button type="submit" class="btn">Add User</button>
                </form>
            </div>

            <!-- Change Password Section -->
            <div class="section">
                <h2 class="section-title">Change User Password</h2>
                <form method="POST">
                    <input type="hidden" name="action" value="change_password">
                    <div class="form-group">
                        <label>Select User:</label>
                        <select name="username" required>
                            <option value="">Select User</option>
                            {% for username in users %}
                            <option value="{{ username }}">{{ username }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>New Password:</label>
                        <input type="password" name="new_password" required>
                    </div>
                    <button type="submit" class="btn">Change Password</button>
                </form>
            </div>

            <!-- Delete User Section -->
            <div class="section">
                <h2 class="section-title">Delete User</h2>
                <form method="POST" onsubmit="return confirmDelete()">
                    <input type="hidden" name="action" value="delete_user">
                    <div class="form-group">
                        <label>Select User to Delete:</label>
                        <select name="username" required>
                            <option value="">Select User</option>
                            {% for username in users %}
                            {% if username != 'master' %}
                            <option value="{{ username }}">{{ username }}</option>
                            {% endif %}
                            {% endfor %}
                        </select>
                    </div>
                    <button type="submit" class="btn danger">Delete User</button>
                </form>
            </div>

            <!-- Current Users Section -->
            <div class="section">
                <h2 class="section-title">Current Users ({{ users|length }})</h2>
                <div class="users-grid">
                    {% for username in users %}
                    <div class="user-card {% if username == 'master' %}master{% endif %}">
                        <strong>{{ username }}</strong>
                        {% if username == 'master' %}
                        <span class="master-badge">MASTER</span>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <script>
        function confirmDelete() {
            const username = document.querySelector('select[name="username"]').value;
            return confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`);
        }
    </script>
</body>
</html>
'''

# Additional HTML templates for SYSTEM_SETTINGS_HTML, SYSTEM_BACKUP_HTML, and SYSTEM_REPORTS_HTML
# would follow the same pattern with comprehensive features

# Vercel serverless function handler
def handler(request, context):
    with app.app_context():
        response = app.full_dispatch_request()
        return {
            'statusCode': response.status_code,
            'headers': dict(response.headers),
            'body': response.get_data(as_text=True)
        }

# For local development
if __name__ == '__main__':
    # Initialize data files if they don't exist
    if not os.path.exists(USERS_FILE):
        save_users(DEFAULT_USERS)
    if not os.path.exists(SYSTEM_SETTINGS_FILE):
        save_system_settings(DEFAULT_SETTINGS)
    
    print("Starting Enhanced Parking Billing System...")
    print("Master Control Panel Features:")
    print("  ✅ User Management (Add/Edit/Delete Users)")
    print("  ✅ System Settings Configuration")
    print("  ✅ Advanced Reporting & Analytics")
    print("  ✅ Data Backup & Export (JSON/CSV)")
    print("  ✅ Revenue Tracking & Statistics")
    print("  ✅ Business Information Management")
    
    app.run(debug=True)
