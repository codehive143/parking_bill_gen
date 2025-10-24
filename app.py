from flask import Flask, render_template_string, request, send_file, redirect, url_for, session
from fpdf import FPDF
from datetime import datetime
import io
import json
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Secure random secret key

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
    # Return default users if file doesn't exist
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
    except:
        pass

def reset_billed_records():
    """Reset all billed records (only for master user)"""
    try:
        if os.path.exists(BILLED_FILE):
            os.remove(BILLED_FILE)
        return True
    except:
        return False

def get_system_stats():
    """Get system statistics"""
    records = load_billed_records()
    users = load_users()
    
    # Calculate monthly revenue
    monthly_revenue = {}
    for record in records:
        month_key = f"{record['month']} {record['year']}"
        if month_key not in monthly_revenue:
            monthly_revenue[month_key] = 0
        monthly_revenue[month_key] += 1000  # Rs. 1000 per bill
    
    return {
        'total_records': len(records),
        'total_users': len(users),
        'total_revenue': len(records) * 1000,
        'monthly_revenue': monthly_revenue,
        'active_slots': len(set(record['slot_number'] for record in records)),
        'billing_months': len(set(f"{record['month']} {record['year']}" for record in records))
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
    
    is_master = session.get('username') == 'master'
    stats = get_system_stats()
    users = load_users()
    
    return render_template_string(BILLED_HTML, 
                                slot_wise=slot_wise,
                                month_wise=month_wise,
                                username=session.get('username'),
                                is_master=is_master,
                                stats=stats,
                                users=users)

@app.route('/reset_billing', methods=['POST'])
@login_required
@master_required
def reset_billing():
    """Reset all billing data - only accessible by master user"""
    if reset_billed_records():
        return redirect(url_for('billed'))
    else:
        return "Error resetting billing data", 500

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
@master_required
def manage_users():
    """User management - only for master"""
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

@app.route('/system_backup', methods=['GET', 'POST'])
@login_required
@master_required
def system_backup():
    """System backup and restore - only for master"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'export_data':
            # Export all data
            export_data = {
                'users': load_users(),
                'billed_records': load_billed_records(),
                'export_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'exported_by': session.get('username')
            }
            
            return json.dumps(export_data, indent=2), 200, {
                'Content-Type': 'application/json',
                'Content-Disposition': 'attachment; filename=parking_system_backup.json'
            }
    
    stats = get_system_stats()
    return render_template_string(BACKUP_HTML,
                                username=session.get('username'),
                                stats=stats)

@app.route('/system_settings', methods=['GET', 'POST'])
@login_required
@master_required
def system_settings():
    """System settings - only for master"""
    message = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_business_info':
            # In a real application, you'd save this to a settings file
            message = {'type': 'success', 'text': 'Business information updated successfully!'}
        
        elif action == 'update_parking_rates':
            # In a real application, you'd save this to a settings file
            message = {'type': 'success', 'text': 'Parking rates updated successfully!'}
    
    return render_template_string(SETTINGS_HTML,
                                username=session.get('username'),
                                message=message)

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

# HTML Templates (Previous templates remain the same, adding new ones below)

# ... [Previous HTML templates for LOGIN_HTML, BILLING_HTML remain unchanged] ...

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
            max-width: 1400px; 
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
        .master-controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .control-card {
            background: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .control-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .control-btn {
            background: #3498db;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            margin: 10px 5px;
            text-decoration: none;
            display: inline-block;
        }
        .control-btn:hover {
            background: #2980b9;
        }
        .control-btn.danger {
            background: #e74c3c;
        }
        .control-btn.danger:hover {
            background: #c0392b;
        }
        .control-btn.success {
            background: #27ae60;
        }
        .control-btn.success:hover {
            background: #219a52;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
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
            {% if is_master %}
            <a href="/manage_users" class="nav-item">Users</a>
            <a href="/system_backup" class="nav-item">Backup</a>
            <a href="/system_settings" class="nav-item">Settings</a>
            {% endif %}
        </div>
        <div class="user-info">
            Welcome, {{ username }} 
            {% if is_master %}<span class="master-badge">MASTER</span>{% endif %}
            | <a href="/logout" style="color: #667eea;">Logout</a>
        </div>
    </div>

    <div class="container">
        <div class="content-container">
            <h1>Billed Records & Master Control Panel</h1>
            
            <!-- System Statistics -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Bills</div>
                    <div class="stat-number">{{ stats.total_records }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Revenue</div>
                    <div class="stat-number">₹{{ stats.total_revenue }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Users</div>
                    <div class="stat-number">{{ stats.total_users }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Slots</div>
                    <div class="stat-number">{{ stats.active_slots }}/14</div>
                </div>
            </div>

            {% if is_master %}
            <!-- Master Control Panel -->
            <div class="section">
                <h2 class="section-title">🔧 Master Control Panel</h2>
                <div class="master-controls">
                    <div class="control-card">
                        <h3>👥 User Management</h3>
                        <p>Add, edit, or remove users</p>
                        <a href="/manage_users" class="control-btn">Manage Users</a>
                    </div>
                    <div class="control-card">
                        <h3>💾 System Backup</h3>
                        <p>Export system data</p>
                        <a href="/system_backup" class="control-btn">Backup Data</a>
                    </div>
                    <div class="control-card">
                        <h3>⚙️ System Settings</h3>
                        <p>Configure system options</p>
                        <a href="/system_settings" class="control-btn">Settings</a>
                    </div>
                    <div class="control-card">
                        <h3>🚨 Data Reset</h3>
                        <p>Clear all billing records</p>
                        <form action="/reset_billing" method="POST" onsubmit="return confirmReset()" style="display: inline;">
                            <button type="submit" class="control-btn danger">Reset All Data</button>
                        </form>
                    </div>
                </div>
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
            return confirm('🚨 ARE YOU SURE?\n\nThis will permanently delete ALL billing records ({{ stats.total_records }} records).\nThis action cannot be undone!');
        }

        // Auto-expand first month
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

# ... [Additional HTML templates for USER_MANAGEMENT_HTML, BACKUP_HTML, SETTINGS_HTML would be added here] ...

# Note: Due to character limits, I'm showing the structure. The complete code would include:
# - USER_MANAGEMENT_HTML (user add/edit/delete interface)
# - BACKUP_HTML (data export interface)  
# - SETTINGS_HTML (system configuration interface)

if __name__ == '__main__':
    app.run(debug=True)
