from flask import Blueprint, make_response, session, flash, redirect
from hostel_pg_management.database.db import get_db
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

report_bp = Blueprint('report', __name__)

@report_bp.before_request
def require_admin():
    if "admin" not in session:
        flash("Please log in as an administrator to download reports.", "warning")
        return redirect("/admin_login")

@report_bp.route("/<report_type>")
def generate_report(report_type):
    db = get_db()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    
    if report_type == "students":
        c.drawString(50, height - 50, "Hostel Management - Resident Roster Report")
        students = db.execute("SELECT name, email, phone FROM students").fetchall()
        
        c.setFont("Helvetica", 12)
        y = height - 100
        for s in students:
            c.drawString(50, y, f"Name: {s['name']} | Email: {s['email']} | Phone: {s['phone']}")
            y -= 25
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 12)
                
    elif report_type == "payments":
        c.drawString(50, height - 50, "Hostel Management - Payment History Report")
        payments = db.execute("SELECT s.name, p.amount, p.payment_date, p.status FROM payments p JOIN students s ON p.student_id=s.id ORDER BY p.payment_date DESC").fetchall()
        
        c.setFont("Helvetica", 12)
        y = height - 100
        for p in payments:
            c.drawString(50, y, f"Resident: {p['name']} | Amt: Rs.{p['amount']} | Date: {p['payment_date']} | Status: {p['status']}")
            y -= 25
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 12)
                
    elif report_type == "complaints":
        c.drawString(50, height - 50, "Hostel Management - Complaints Report")
        complaints = db.execute("SELECT s.name, c.subject, c.status, c.created_at FROM complaints c JOIN students s ON c.student_id=s.id ORDER BY c.created_at DESC").fetchall()
        
        c.setFont("Helvetica", 10)
        y = height - 100
        for cp in complaints:
            c.drawString(50, y, f"Date: {cp['created_at'][:10]} | Resident: {cp['name']} | Subject: {cp['subject']} | Status: {cp['status']}")
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
    else:
        c.drawString(50, height - 50, "Report Not Found")

    c.save()
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report.pdf'
    return response
