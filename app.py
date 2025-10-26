from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import csv
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "admin_secret"
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

BILLS_CSV = os.path.join(app.config["UPLOAD_FOLDER"], "bills.csv")

# ✅ Ensure CSV file exists
if not os.path.exists(BILLS_CSV):
    with open(BILLS_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["BillID", "CustomerName", "VehicleNo", "SlotNo", "Hours", "RatePerHour", "Total", "Date"])


# ✅ Helper Functions
def read_bills():
    with open(BILLS_CSV, newline="") as f:
        return list(csv.DictReader(f))

def write_bills(bills):
    with open(BILLS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["BillID", "CustomerName", "VehicleNo", "SlotNo", "Hours", "RatePerHour", "Total", "Date"])
        writer.writeheader()
        writer.writerows(bills)


# ✅ Home Route - Dashboard
@app.route('/')
def home():
    bills = read_bills()
    total_revenue = sum(float(b["Total"]) for b in bills)
    total_cars = len(bills)
    occupied_slots = {b["SlotNo"] for b in bills}
    available_slots = [str(i) for i in range(1, 21) if str(i) not in occupied_slots]
    return render_template("dashboard.html",
                           bills=bills,
                           total_revenue=total_revenue,
                           total_cars=total_cars,
                           available_slots=available_slots)


# ✅ Add Bill
@app.route('/add', methods=['POST'])
def add_bill():
    bills = read_bills()
    new_id = str(len(bills) + 1)
    name = request.form["name"]
    vehicle = request.form["vehicle"]
    slot = request.form["slot"]
    hours = float(request.form["hours"])
    rate = float(request.form["rate"])
    total = hours * rate
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    bills.append({
        "BillID": new_id,
        "CustomerName": name,
        "VehicleNo": vehicle,
        "SlotNo": slot,
        "Hours": hours,
        "RatePerHour": rate,
        "Total": total,
        "Date": date
    })
    write_bills(bills)
    flash("✅ Bill added successfully!", "success")
    return redirect(url_for('home'))


# ✅ Edit Bill
@app.route('/edit/<bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    bills = read_bills()
    bill = next((b for b in bills if b["BillID"] == bill_id), None)
    if not bill:
        flash("❌ Bill not found!", "danger")
        return redirect(url_for('home'))

    if request.method == "POST":
        bill["CustomerName"] = request.form["name"]
        bill["VehicleNo"] = request.form["vehicle"]
        bill["SlotNo"] = request.form["slot"]
        bill["Hours"] = request.form["hours"]
        bill["RatePerHour"] = request.form["rate"]
        bill["Total"] = float(bill["Hours"]) * float(bill["RatePerHour"])
        write_bills(bills)
        flash("✏️ Bill updated successfully!", "info")
        return redirect(url_for('home'))

    return render_template("edit.html", bill=bill)


# ✅ Delete Bill
@app.route('/delete/<bill_id>')
def delete_bill(bill_id):
    bills = [b for b in read_bills() if b["BillID"] != bill_id]
    write_bills(bills)
    flash("🗑️ Bill deleted!", "danger")
    return redirect(url_for('home'))


# ✅ Generate PDF for Bill
@app.route('/pdf/<bill_id>')
def generate_pdf(bill_id):
    bills = read_bills()
    bill = next((b for b in bills if b["BillID"] == bill_id), None)
    if not bill:
        flash("❌ Bill not found!", "danger")
        return redirect(url_for('home'))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt=f"Parking Bill #{bill['BillID']}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    for k, v in bill.items():
        pdf.cell(200, 10, txt=f"{k}: {v}", ln=True)

    filename = os.path.join(app.config["UPLOAD_FOLDER"], f"bill_{bill_id}.pdf")
    pdf.output(filename)
    return send_file(filename, as_attachment=True)


# ✅ Download CSV (Export All Bills)
@app.route('/download')
def download_csv():
    return send_file(BILLS_CSV, as_attachment=True)


# ✅ Master Reset Section — Final Version
@app.route('/reset_all', methods=['POST'])
def reset_all():
    # Clear all bills and reset file
    with open(BILLS_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["BillID", "CustomerName", "VehicleNo", "SlotNo", "Hours", "RatePerHour", "Total", "Date"])
    flash("⚠️ All data has been reset successfully by Master!", "warning")
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
