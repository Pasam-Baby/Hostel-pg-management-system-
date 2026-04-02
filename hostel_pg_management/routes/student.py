import io
import os
from datetime import datetime

from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, session, jsonify
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from hostel_pg_management.database.db import get_db

student_bp = Blueprint('student', __name__)


@student_bp.before_request
def require_student():
    if 'student_id' not in session:
        flash('Please log in as a user.', 'warning')
        return redirect('/student_login')


@student_bp.route('/dashboard')
def dashboard():
    db = get_db()
    sid = session['student_id']
    total_complaints = db.execute('SELECT COUNT(*) FROM complaints WHERE student_id=?', (sid,)).fetchone()[0]
    # Treat both 'Resolved' and 'Solved' as resolved for display purposes
    resolved_complaints = db.execute("SELECT COUNT(*) FROM complaints WHERE student_id=? AND (status='Resolved' OR status='Solved')", (sid,)).fetchone()[0]
    payment_count = db.execute('SELECT COUNT(*) FROM payments WHERE student_id=?', (sid,)).fetchone()[0]
    # Sum of payments by the student
    try:
        payments_sum_row = db.execute('SELECT SUM(amount) as total_paid FROM payments WHERE student_id=?', (sid,)).fetchone()
        payments_sum = payments_sum_row['total_paid'] or 0
    except Exception:
        payments_sum = 0
    room_data = db.execute('SELECT rooms.room_no, rooms.price FROM students LEFT JOIN rooms ON students.room_id = rooms.id WHERE students.id=?', (sid,)).fetchone()
    room_no = room_data['room_no'] if room_data and room_data['room_no'] else 'Unassigned'
    recent_complaints = db.execute('SELECT subject, status, created_at FROM complaints WHERE student_id=? ORDER BY created_at DESC LIMIT 3', (sid,)).fetchall()
    recent_payments = db.execute('SELECT amount, payment_date FROM payments WHERE student_id=? ORDER BY payment_date DESC LIMIT 6', (sid,)).fetchall()
    # Prepare payment chart arrays (chronological order)
    payment_dates = []
    payment_amounts = []
    try:
        for row in reversed(recent_payments):
            payment_dates.append(row['payment_date'])
            payment_amounts.append(row['amount'])
    except Exception:
        payment_dates = []
        payment_amounts = []

    current_month_prefix = datetime.now().strftime('%Y-%m')
    current_date_str = datetime.now().strftime('%Y-%m-%d')
    due_date = f"{current_month_prefix}-05"
    
    paid_this_month = db.execute('SELECT id FROM payments WHERE student_id=? AND (payment_date LIKE ? OR payment_month = ?)', (sid, f'{current_month_prefix}%', current_month_prefix)).fetchone()
    rent_due = paid_this_month is None
    
    # Calculate late fee based on current date vs 5th of the month
    late_fee = 0
    if rent_due:
        from datetime import date
        today = date.today()
        due = date(today.year, today.month, 5)
        if today > due:
            late_fee = (today - due).days * 50
    # Add rooms list and quick counts for dashboard cards (view-only)
    try:
        rooms_rows = db.execute('SELECT id, room_no, ac_type, status, available_beds FROM rooms ORDER BY CAST(room_no AS INTEGER) ASC').fetchall()
        rooms = [dict(r) for r in rooms_rows] if rooms_rows else []
    except Exception:
        rooms = []

    try:
        total_rooms = db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]
    except Exception:
        total_rooms = 0

    try:
        my_bookings = db.execute('SELECT COUNT(*) FROM bookings WHERE LOWER(email) = LOWER((SELECT email FROM students WHERE id=?))', (sid,)).fetchone()[0]
    except Exception:
        my_bookings = 0

    try:
        available_beds_count = db.execute('SELECT SUM(available_beds) FROM rooms').fetchone()[0] or 0
    except Exception:
        available_beds_count = 0

    # Visitor requests counts for this student
    try:
        visits_total = db.execute('SELECT COUNT(*) FROM visits WHERE student_id = ?', (sid,)).fetchone()[0]
        visits_pending = db.execute("SELECT COUNT(*) FROM visits WHERE student_id = ? AND (status='Pending' OR status IS NULL OR status='')", (sid,)).fetchone()[0]
        visits_approved = db.execute("SELECT COUNT(*) FROM visits WHERE student_id = ? AND (status='Accepted' OR status='Approved')", (sid,)).fetchone()[0]
    except Exception:
        visits_total = visits_pending = visits_approved = 0

    return render_template(
        'student_dashboard.html',
        total_complaints=total_complaints,
        resolved_complaints=resolved_complaints,
        payment_count=payment_count,
        room_no=room_no,
            recent_complaints=recent_complaints,
            recent_payments=recent_payments,
        student_name=session.get('student_name'),
        rent_due=rent_due,
        late_fee=late_fee,
        current_day=datetime.now().day,
        payment_dates=payment_dates,
        payment_amounts=payment_amounts,
        available_rooms_count=available_beds_count,
        visits_total=visits_total,
        visits_pending=visits_pending,
        payments_sum=payments_sum,
        student_id=sid,
        # new additions
        rooms=rooms,
        total_rooms=total_rooms,
        my_bookings=my_bookings,
        visits_approved=visits_approved,
    )


@student_bp.route('/room')
def room():
    db = get_db()
    room_data = db.execute(
        '''
        SELECT rooms.id AS id, rooms.room_no, rooms.total_beds, rooms.occupied, rooms.available_beds, rooms.price, rooms.ac_type, rooms.sharing_type, rooms.category
        FROM students JOIN rooms ON students.room_id = rooms.id
        WHERE students.id = ?
        ''',
        (session['student_id'],),
    ).fetchone()
    # compute floor from room_no when possible (e.g., '101' -> floor 1)
    room = None
    try:
        if room_data:
            room = dict(room_data)
            rn = room.get('room_no')
            floor = None
            try:
                if rn and rn.isdigit() and len(rn) >= 3:
                    floor = int(rn) // 100
                else:
                    # fallback: first character as floor when room_no has pattern like '1A'
                    if rn and len(rn) >= 1 and rn[0].isdigit():
                        floor = int(rn[0])
            except Exception:
                floor = None
            room['floor'] = floor
    except Exception:
        room = room_data

    return render_template('student_room.html', room=room)


@student_bp.route('/visits')
def visits():
    """Show logged-in student's visit requests and their statuses."""
    db = get_db()
    sid = session['student_id']
    # Try to match by student_id first; fall back to email/phone if student_id not linked
    try:
        visits_list = db.execute('SELECT * FROM visits WHERE student_id = ? ORDER BY visit_date DESC, visit_time DESC', (sid,)).fetchall()
        if not visits_list:
            # try matching by student's email/phone
            student = db.execute('SELECT email, phone FROM students WHERE id = ?', (sid,)).fetchone()
            if student:
                visits_list = db.execute('SELECT * FROM visits WHERE LOWER(email)=LOWER(?) OR phone=? ORDER BY visit_date DESC, visit_time DESC', (student['email'], student['phone'])).fetchall()
    except Exception:
        visits_list = []
    # Normalize status values for display (some older records may use 'Accepted')
    try:
        for v in visits_list:
            if v.get('status') == 'Accepted':
                v['status'] = 'Approved'
    except Exception:
        pass
    # Enrich visits with room number and the student name they are visiting (usually the logged-in student)
    enriched = []
    try:
        # fetch current student's own info to show "for" field clearly
        me = db.execute('SELECT id, name, room_id FROM students WHERE id=?', (sid,)).fetchone()
        my_name = me['name'] if me and 'name' in me.keys() else None
        my_room_no = None
        if me and me.get('room_id'):
            rn = db.execute('SELECT room_no FROM rooms WHERE id=?', (me['room_id'],)).fetchone()
            my_room_no = rn['room_no'] if rn else None
        for v in visits_list:
            vd = dict(v)
            # if visit linked to a student, fetch that student's name/room
            sid_link = vd.get('student_id')
            if sid_link:
                srow = db.execute('SELECT s.name, r.room_no FROM students s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id=?', (sid_link,)).fetchone()
                vd['for_name'] = srow['name'] if srow and 'name' in srow.keys() else (vd.get('person_to_visit') or my_name)
                vd['for_room'] = srow['room_no'] if srow and 'room_no' in srow.keys() else (vd.get('for_room_no') or my_room_no)
            else:
                # if the visitor provided a person_to_visit or for_room_no, use those; else default to current student
                vd['for_name'] = vd.get('person_to_visit') or my_name
                vd['for_room'] = vd.get('for_room_no') or my_room_no
            enriched.append(vd)
    except Exception:
        enriched = [dict(v) for v in visits_list]

    return render_template('student_visits.html', visits=enriched)


@student_bp.route('/notifications')
def notifications():
    """Show notifications for the logged-in student."""
    db = get_db()
    sid = session['student_id']
    try:
        notes = db.execute(
            "SELECT * FROM notifications WHERE (user_type='public' OR (user_type='student' AND user_id=?)) ORDER BY created_at DESC",
            (sid,),
        ).fetchall()
        # After showing notifications to the student, mark them as read
        try:
            db.execute("UPDATE notifications SET is_read=1 WHERE user_type='student' AND user_id=? AND is_read=0", (sid,))
            db.commit()
        except Exception:
            pass
    except Exception:
        notes = []
    return render_template('student_notifications.html', notifications=notes)


@student_bp.route('/book_room')
def book_room():
    return render_template('book_room.html')


@student_bp.route('/notifications/delete/<int:notif_id>', methods=['POST'])
def delete_notification(notif_id):
    """Delete a single notification by its ID for the logged-in student."""
    db = get_db()
    sid = session.get('student_id')
    if not sid:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        # Only allow deleting notifications that belong to this student or are public
        db.execute(
            "DELETE FROM notifications WHERE id=? AND (user_type='public' OR (user_type='student' AND user_id=?))",
            (notif_id, sid),
        )
        db.commit()
        return jsonify({'success': True})
    except Exception:
        return jsonify({'success': False}), 500

@student_bp.route('/notifications/clear', methods=['POST'])
def clear_notifications():
    """Clear or mark as read student-specific notifications for the logged-in student.

    This endpoint is called when the user views/opens their notifications so that
    student-only notifications do not appear again for that student.
    """
    db = get_db()
    sid = session.get('student_id')
    if not sid:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        # Prefer deleting student-scoped notifications (keeps public notices intact)
        db.execute("DELETE FROM notifications WHERE user_type='student' AND user_id=?", (sid,))
        db.commit()
        return jsonify({'success': True})
    except Exception:
        # Best-effort fallback: mark as read
        try:
            db.execute("UPDATE notifications SET is_read=1 WHERE user_type='student' AND user_id=? AND is_read=0", (sid,))
            db.commit()
            return jsonify({'success': True})
        except Exception:
            return jsonify({'success': False}), 500


@student_bp.route('/complaints', methods=['GET', 'POST'])
def complaints():
    db = get_db()
    if request.method == 'POST':
        subject = request.form.get('subject')
        complaint = request.form.get('complaint')
        db.execute('INSERT INTO complaints (student_id, subject, complaint) VALUES (?, ?, ?)', (session['student_id'], subject, complaint))
        db.commit()
        flash('Complaint submitted.', 'success')
        return redirect('/student/complaints')

    complaints_list = db.execute(
        'SELECT subject, complaint, status, created_at FROM complaints WHERE student_id=? ORDER BY created_at DESC',
        (session['student_id'],),
    ).fetchall()
    return render_template('view_complaints.html', complaints=complaints_list)


@student_bp.route('/payments')
def payments():
    db = get_db()
    payments_list = db.execute(
        'SELECT id, amount, payment_date, due_date, late_fee, status FROM payments WHERE student_id=? ORDER BY payment_date DESC',
        (session['student_id'],),
    ).fetchall()
    return render_template('student_payments.html', payments=payments_list)


@student_bp.route('/download_receipt/<int:payment_id>')
def download_receipt(payment_id):
    db = get_db()
    sid = session['student_id']
    payment = db.execute(
        '''
        SELECT p.amount, p.payment_date, p.status, p.late_fee, s.name, s.email
        FROM payments p
        JOIN students s ON p.student_id=s.id
        WHERE p.id=? AND p.student_id=?
        ''',
        (payment_id, sid),
    ).fetchone()
    if not payment:
        flash('Receipt not found or permission denied.', 'danger')
        return redirect('/student/payments')

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont('Helvetica-Bold', 18)
    c.drawString(50, height - 50, 'Hostel Management System')
    c.setFont('Helvetica', 14)
    c.drawString(50, height - 80, 'Official Payment Receipt')
    c.line(50, height - 90, width - 50, height - 90)
    c.setFont('Helvetica', 12)
    c.drawString(50, height - 120, f'Receipt No: #{payment_id}')
    c.drawString(50, height - 145, f'Date: {payment["payment_date"]}')
    c.drawString(50, height - 170, f'User Name: {payment["name"]}')
    c.drawString(50, height - 195, f'Email: {payment["email"]}')
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, height - 235, f'Amount Paid: Rs. {payment["amount"]}')
    c.drawString(50, height - 260, f'Late Fee: Rs. {payment["late_fee"] or 0}')
    c.drawString(50, height - 285, f'Status: {payment["status"]}')
    c.line(50, height - 305, width - 50, height - 305)
    c.setFont('Helvetica-Oblique', 10)
    c.drawString(50, height - 335, 'Thank you for your payment.')
    c.drawString(50, height - 355, 'This is a computer-generated receipt.')
    c.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Receipt_{payment_id}.pdf'
    return response


@student_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        id_proof = request.files.get('id_proof')
        id_proof_path = None
        if id_proof and id_proof.filename:
            filename = secure_filename(id_proof.filename)
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            saved_path = os.path.join(upload_folder, filename)
            id_proof.save(saved_path)
            id_proof_path = f'uploads/{filename}'
            db.execute('UPDATE students SET id_proof=?, is_verified=0 WHERE id=?', (id_proof_path, session['student_id']))

        db.execute('UPDATE students SET name=?, phone=? WHERE id=?', (name, phone, session['student_id']))
        db.commit()
        session['student_name'] = name
        flash('Profile updated successfully.', 'success')
        return redirect('/student/dashboard')

    student_data = db.execute('SELECT name, email, phone, id_proof, is_verified FROM students WHERE id=?', (session['student_id'],)).fetchone()
    return render_template('student_profile.html', student=student_data)


@student_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        old = request.form.get('old_password')
        new = request.form.get('new_password')
        db = get_db()
        student = db.execute('SELECT * FROM students WHERE id=?', (session['student_id'],)).fetchone()
        if student and check_password_hash(student['password'], old):
            new_hash = generate_password_hash(new)
            db.execute('UPDATE students SET password=? WHERE id=?', (new_hash, session['student_id']))
            db.commit()
            flash('Password changed successfully', 'success')
        else:
            flash('Old password incorrect', 'danger')
    return render_template('student_change_password.html')
