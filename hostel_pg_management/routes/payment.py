import os
import tempfile
from urllib.parse import quote_plus
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from hostel_pg_management.database.db import get_db
# Import ensure_booking_user to create/lookup student for booking payments
from hostel_pg_management.routes.booking import ensure_booking_user
from hostel_pg_management.utils.sms import send_sms

payment_bp = Blueprint('payment', __name__)


def calculate_late_fee(due_date, payment_date):
    try:
        due = datetime.strptime(due_date, '%Y-%m-%d').date()
        pay = datetime.strptime(payment_date, '%Y-%m-%d').date()
        if pay > due:
            return (pay - due).days * 50
    except ValueError:
        return 0
    return 0


def add_notification(db, user_type, user_id, message, notification_type='info'):
    try:
        db.execute(
            "INSERT INTO notifications (user_type, user_id, message, notification_type) VALUES (?, ?, ?, ?)",
            (user_type, user_id, message, notification_type),
        )
        try:
            db.commit()
        except Exception:
            pass
    except Exception:
        # Best-effort: do not break payment flow if notifications fail
        pass


def generate_receipt_pdf(payment):
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.close()
        c = canvas.Canvas(temp_file.name, pagesize=letter)
        width, height = letter

        c.setFont('Helvetica-Bold', 20)
        c.drawString(50, height - 50, 'Hostel Management - Payment Receipt')
        c.setFont('Helvetica', 12)

        total_amount = payment['amount'] + (payment['late_fee'] or 0)
        details = [
            f"Receipt ID: PAY{payment['id']:04d}",
            f"Resident ID: {payment['student_id']}",
            f"Payment Month: {payment['payment_month']}",
            f"Amount Paid: Rs. {payment['amount']}",
            f"Late Fee: Rs. {payment['late_fee'] or 0} (Rs. 50/day)",
            f"Total Amount: Rs. {total_amount}",
            f"Payment Date: {payment['payment_date']}",
            f"Due Date: {payment['due_date']}",
            f"Status: {payment['status']}",
        ]

        y_position = height - 100
        for detail in details:
            c.drawString(50, y_position, detail)
            y_position -= 20

        c.setFont('Helvetica-Oblique', 10)
        c.drawString(50, 60, 'Thank you for your payment.')
        c.drawString(50, 40, 'Hostel Management System - Digital Receipt')
        c.save()
        return temp_file.name
    except Exception as e:
        print(f'Error generating PDF: {e}')
        return None


@payment_bp.route('/payment')
def payment_dashboard():
    if 'student_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('auth.student_login'))

    db = get_db()
    student_id = session['student_id']
    payments = db.execute(
        '''
        SELECT * FROM payments
        WHERE student_id = ?
        ORDER BY payment_month DESC, payment_date DESC
        ''',
        (student_id,),
    ).fetchall()
    student = db.execute(
        '''
        SELECT s.*, r.price, r.room_no, r.sharing_type, r.ac_type
        FROM students s
        LEFT JOIN rooms r ON s.room_id = r.id
        WHERE s.id = ?
        ''',
        (student_id,),
    ).fetchone()

    current_month = datetime.now().strftime('%Y-%m')
    # Gather payments for this student and compute totals for the current month
    monthly_payments = db.execute(
        'SELECT * FROM payments WHERE student_id = ? AND payment_month = ?',
        (student_id, current_month),
    ).fetchall()

    total_paid = sum(p['amount'] for p in monthly_payments if p['status'] == 'Paid') if monthly_payments else 0

    due_date = f'{current_month}-05'
    monthly_rent = student['price'] if student and student['price'] else 5000
    projected_late_fee = 0 if total_paid >= monthly_rent else calculate_late_fee(due_date, datetime.now().strftime('%Y-%m-%d'))
    total_amount = monthly_rent + projected_late_fee

    # Add a payment reminder notification if unpaid and not already created for this month
    if total_paid < monthly_rent:
        try:
            existing_note = db.execute(
                "SELECT * FROM notifications WHERE user_type='student' AND user_id=? AND message LIKE ?",
                (student_id, f"%{current_month}%"),
            ).fetchone()
            if not existing_note:
                add_notification(db, 'student', student_id, f'Reminder: Rent for {current_month} is due on {due_date}.', 'warning')
                db.commit()
        except Exception:
            pass

    # Payment contact and QR (configurable via PAYMENT_PHONE env)
    payment_phone = os.environ.get('PAYMENT_PHONE') or (student['phone'] if student and 'phone' in student and student['phone'] else '')
    qr_url = ''
    if payment_phone:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={quote_plus(payment_phone)}"

    return render_template(
        'payment.html',
        payments=payments,
        student=student,
        monthly_rent=monthly_rent,
        due_date=due_date,
        projected_late_fee=projected_late_fee,
        total_amount=total_amount,
        total_paid=total_paid,
        current_month=current_month,
        monthly_payments=monthly_payments,
        payment_phone=payment_phone,
        payment_qr=qr_url,
    )


@payment_bp.route('/payment/pay', methods=['POST'])
def make_payment():
    if 'student_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('auth.student_login'))

    db = get_db()
    student_id = session['student_id']
    student = db.execute(
        '''
        SELECT s.*, r.price
        FROM students s
        LEFT JOIN rooms r ON s.room_id = r.id
        WHERE s.id = ?
        ''',
        (student_id,),
    ).fetchone()

    if not student:
        flash('User not found', 'danger')
        return redirect(url_for('payment.payment_dashboard'))

    # Allow optional amount and payment_month from form (for partial payments or paying past months)
    try:
        form_amount = request.form.get('amount')
        if form_amount:
            amount = int(float(form_amount))
        else:
            amount = int(student['price'] or 5000)
    except Exception:
        flash('Invalid payment amount provided.', 'danger')
        return redirect(url_for('payment.payment_dashboard'))

    pm = request.form.get('payment_month')
    now = datetime.now()
    payment_month = pm if pm else now.strftime('%Y-%m')
    payment_date = now.strftime('%Y-%m-%d')
    due_date = f'{payment_month}-05'
    late_fee = calculate_late_fee(due_date, payment_date)

    if amount <= 0:
        flash('Payment amount must be greater than zero.', 'danger')
        return redirect(url_for('payment.payment_dashboard'))

    # Insert a new payment record (allow multiple payments per month)
    try:
        db.execute(
            '''
            INSERT INTO payments (student_id, amount, payment_month, payment_date, due_date, status, late_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (student_id, amount, payment_month, payment_date, due_date, 'Paid', late_fee),
        )
        db.commit()
    except Exception as e:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- payment.make_payment DB error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        flash('Failed to record payment. Please try again or contact admin.', 'danger')
        return redirect(url_for('payment.payment_dashboard'))

    # Add student notification for payment
    try:
        add_notification(db, 'student', student_id, f'Payment of Rs. {amount + late_fee} received for {payment_month}', 'success')
        db.commit()
    except Exception:
        pass
        
    try:
        if student and 'phone' in student and student['phone']:
            send_sms(student['phone'], f'Payment of Rs. {amount + late_fee} successful for {payment_month}')
    except Exception:
        pass

    flash(f'Payment of Rs. {amount + late_fee} successful for {payment_month}', 'success')
    return redirect(url_for('payment.payment_dashboard'))


@payment_bp.route('/payment/receipt/<int:payment_id>')
def download_receipt(payment_id):
    db = get_db()
    
    # Check if user is logged in
    student_id = session.get('student_id')
    
    # Allow download if the user just made this payment during booking
    if not student_id and session.get('last_payment_id') == payment_id:
        payment = db.execute('SELECT * FROM payments WHERE id = ?', (payment_id,)).fetchone()
    elif student_id:
        payment = db.execute('SELECT * FROM payments WHERE id = ? AND student_id = ?', (payment_id, student_id)).fetchone()
    else:
        flash('Please login first', 'danger')
        return redirect(url_for('auth.student_login'))

    if not payment:
        flash('Payment not found or access denied', 'danger')
        return redirect(url_for('payment.payment_dashboard'))

    pdf_path = generate_receipt_pdf(payment)
    if pdf_path and os.path.exists(pdf_path):
        try:
            return send_file(pdf_path, as_attachment=True, download_name=f"receipt_{payment['payment_month']}.pdf")
        finally:
            try:
                os.unlink(pdf_path)
            except OSError:
                pass

    flash('Error generating receipt', 'danger')
    return redirect(url_for('payment.payment_dashboard'))


@payment_bp.route('/payment/book/<booking_id>', methods=['GET', 'POST'])
def pay_booking(booking_id):
    """Allow paying for a booking by booking ID (works for users before account creation)."""
    db = get_db()
    # Look up booking by its external booking_id (e.g., BK1234)
    booking = db.execute('SELECT * FROM bookings WHERE booking_id = ?', (booking_id,)).fetchone()
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('booking.book_room'))

    if request.method == 'POST':
        # Determine amount to pay (allow partial)
        try:
            form_amount = request.form.get('amount')
            if form_amount:
                amount = int(float(form_amount))
            else:
                amount = int(booking['price'] or 0)
        except Exception:
            flash('Invalid payment amount provided.', 'danger')
            return redirect(url_for('payment.pay_booking', booking_id=booking_id))

        if amount <= 0:
            flash('Payment amount must be greater than zero.', 'danger')
            return redirect(url_for('payment.pay_booking', booking_id=booking_id))

        # Ensure a student record exists for this booking (creates if missing)
        try:
            user, temp_password = ensure_booking_user(booking, verified=False)
            student_id = user['id']
        except Exception:
            # As a fallback, try to find any student with same email
            student = db.execute('SELECT * FROM students WHERE LOWER(email)=LOWER(?)', (booking['email'],)).fetchone()
            student_id = student['id'] if student else None

        payment_month = datetime.now().strftime('%Y-%m')
        payment_date = datetime.now().strftime('%Y-%m-%d')
        due_date = f"{payment_month}-05"
        late_fee = calculate_late_fee(due_date, payment_date)

        if not student_id:
            flash('Failed to associate payment with a user account.', 'danger')
            return redirect(url_for('payment.pay_booking', booking_id=booking_id))

        # Insert payment record linked to booking
        try:
            db.execute(
                '''
                INSERT INTO payments (student_id, booking_id, amount, payment_month, payment_date, due_date, status, late_fee)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (student_id, booking['id'], amount, payment_month, payment_date, due_date, 'Paid', late_fee),
            )
            db.commit()
            # fetch the inserted payment so we can show/download receipt on the booking success page
            try:
                payment_record = db.execute(
                    'SELECT * FROM payments WHERE booking_id = ? ORDER BY id DESC LIMIT 1',
                    (booking['id'],),
                ).fetchone()
                receipt_id = payment_record['id'] if payment_record else None
            except Exception:
                receipt_id = None
        except Exception:
            import traceback
            with open('server_errors.log', 'a', encoding='utf-8') as fh:
                fh.write('\n--- payment.pay_booking DB error ---\n')
                fh.write(traceback.format_exc())
                fh.write('\n')
            flash('Failed to record payment. Please try again or contact admin.', 'danger')
            return redirect(url_for('payment.pay_booking', booking_id=booking_id))

        try:
            add_notification(db, 'student', student_id, f'Payment of Rs. {amount + late_fee} received for booking {booking_id}', 'success')
            db.commit()
        except Exception:
            pass
            
        try:
            if booking and 'phone' in booking and booking['phone']:
                send_sms(booking['phone'], f'Payment of Rs. {amount + late_fee} successful for booking {booking_id}')
        except Exception:
            pass

        flash(f'Payment of Rs. {amount + late_fee} successful for booking {booking_id}', 'success')
        if receipt_id:
            session['last_payment_id'] = receipt_id
            return redirect(url_for('booking.booking_success', booking_id=booking_id, receipt_id=receipt_id))
        else:
            return redirect(url_for('booking.booking_success', booking_id=booking_id))

    # GET: show a minimal payment form with booking summary
    payment_phone = os.environ.get('PAYMENT_PHONE') or (booking['phone'] if booking and 'phone' in booking and booking['phone'] else '')
    payment_qr = ''
    if payment_phone:
        payment_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={quote_plus(payment_phone)}"

    return render_template('pay_booking.html', booking=booking, payment_phone=payment_phone, payment_qr=payment_qr)


@payment_bp.route('/admin/payments')
def admin_payments():
    if 'admin' not in session:
        flash('Please login as admin', 'danger')
        return redirect(url_for('auth.admin_login'))

    db = get_db()
    payments = db.execute(
        '''
        SELECT p.*, s.name, s.email
        FROM payments p
        LEFT JOIN students s ON p.student_id = s.id
        ORDER BY p.payment_month DESC, p.payment_date DESC
        ''',
    ).fetchall()
    return render_template('payments.html', payments=payments, students=[])


@payment_bp.route('/admin/payment/<int:payment_id>/update', methods=['POST'])
def update_payment_status(payment_id):
    if 'admin' not in session:
        flash('Please login as admin', 'danger')
        return redirect(url_for('auth.admin_login'))

    db = get_db()
    status = request.form.get('status')
    db.execute('UPDATE payments SET status = ? WHERE id = ?', (status, payment_id))
    db.commit()

    flash('Payment status updated', 'success')
    return redirect(url_for('payment.admin_payments'))
