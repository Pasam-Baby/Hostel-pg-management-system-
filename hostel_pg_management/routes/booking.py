from flask import Blueprint, flash, redirect, render_template, request, session, url_for
import os
from urllib.parse import quote_plus
from hostel_pg_management.database.db import get_db
from datetime import datetime
import random

from werkzeug.security import generate_password_hash

from hostel_pg_management.utils.mail import send_email
from datetime import timedelta

booking_bp = Blueprint('booking', __name__)

def generate_booking_id():
    """Generate unique booking ID"""
    prefix = "BK"
    number = random.randint(101, 9999)
    return f"{prefix}{number}"

def get_room_price(sharing_type, ac_type):
    """Get room price based on sharing type and AC option"""
    prices = {
        (1, 'AC'): 9000,
        (1, 'Non-AC'): 6000,
        (2, 'AC'): 7500,
        (2, 'Non-AC'): 6000,
        (3, 'AC'): 6500,
        (3, 'Non-AC'): 5500,
        (4, 'AC'): 6000,
        (4, 'Non-AC'): 5000,
    }
    # Return canonical price for the given configuration, or a sensible default
    return prices.get((sharing_type, ac_type), 6000)


def add_notification(user_type, user_id, message, notification_type='info'):
    db = get_db()
    db.execute(
        """
        INSERT INTO notifications (user_type, user_id, message, notification_type)
        VALUES (?, ?, ?, ?)
        """,
        (user_type, user_id, message, notification_type),
    )
    try:
        db.commit()
    except Exception:
        # best effort; do not break booking flow if commit fails
        pass


def ensure_booking_user(booking, verified=False):
    db = get_db()
    user = db.execute("SELECT * FROM students WHERE LOWER(email)=LOWER(?)", (booking['email'],)).fetchone()
    if user:
        if not user['room_id'] and booking['room_id']:
            db.execute("UPDATE students SET room_id=? WHERE id=?", (booking['room_id'], user['id']))
        try:
            is_verified_val = user['is_verified']
        except Exception:
            is_verified_val = 0
        if verified and not is_verified_val:
            db.execute("UPDATE students SET is_verified = 1, approved = 1 WHERE id = ?", (user['id'],))
        # refresh user record
        user = db.execute("SELECT * FROM students WHERE id = ?", (user['id'],)).fetchone()
        return user, None

    temp_password = booking['booking_id']
    # Prefer a user-supplied password if provided with the booking
    try:
        if booking and booking['password_hash']:
            password_hash = booking['password_hash']
        else:
            password_hash = generate_password_hash(temp_password)
    except Exception:
        password_hash = generate_password_hash(temp_password)
    verified_flag = 1 if verified else 0
    db.execute(
        """
        INSERT INTO students (name, email, password, phone, room_id, is_verified, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (booking['name'], booking['email'], password_hash, booking['phone'], booking['room_id'], verified_flag, verified_flag),
    )
    user = db.execute("SELECT * FROM students WHERE LOWER(email)=LOWER(?)", (booking['email'],)).fetchone()
    return user, temp_password

@booking_bp.route('/book', methods=['GET', 'POST'])
def book_room():
    # Debug entry log
    try:
        with open('booking_entry.log','a', encoding='utf-8') as fh:
            fh.write(f"book_room entered; method={request.method}\n")
    except Exception:
        pass
    # Handle booking form submission or render booking page
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        create_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        room_id = request.form.get('room_id')
        # Initialize room variable early so price lookup can reference it safely
        room = None
        if room_id:
            try:
                room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
                if room and room['available_beds'] <= 0:
                    room = None
            except Exception:
                room = None
        try:
            sharing_type = int(request.form.get('sharing_type'))
        except Exception:
            sharing_type = None
        ac_type = request.form.get('ac_type')

        # Allow booking with only name and phone (email optional). If email missing, create placeholder.
        if not email or '@' not in email:
            email = f"{phone}@noemail.local"

        if not all([name, phone, request.form.get('sharing_type'), ac_type]):
            flash('All booking fields are required', 'danger')
            return redirect(url_for('booking.book_room'))

        # If password fields provided, validate match
        password_hash_to_store = None
        if create_password or confirm_password:
            if create_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('booking.book_room'))
            # store hashed password in booking for later use when creating student
            password_hash_to_store = generate_password_hash(create_password)

        # Determine price from selected room (admin-defined) when available,
        # otherwise try to pick price from any matching room in DB and fall back to mapping.
        try:
            room_price = None
            if room and room['price'] is not None:
                room_price = room['price']
            if not room_price:
                # try to find a room with same sharing/ac and available beds to derive price
                candidate = db.execute(
                    "SELECT price FROM rooms WHERE sharing_type = ? AND ac_type = ? AND available_beds > 0 LIMIT 1",
                    (sharing_type, ac_type),
                ).fetchone()
                if candidate and candidate['price'] is not None:
                    room_price = candidate['price']
            if room_price is None:
                price = get_room_price(sharing_type, ac_type)
            else:
                price = int(room_price)
        except Exception:
            price = get_room_price(sharing_type, ac_type)

        # If a specific room_id was provided, `room` was already resolved above.

        # Otherwise find any available room matching preferences
        if not room:
            room = db.execute(
                "SELECT * FROM rooms WHERE sharing_type = ? AND ac_type = ? AND available_beds > 0 LIMIT 1",
                (sharing_type, ac_type)
            ).fetchone()

        if not room:
            flash('No rooms available for the selected configuration', 'warning')
            return redirect(url_for('booking.book_room'))

        # Generate booking ID
        booking_id = generate_booking_id()

        # Ensure unique booking ID
        while db.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone():
            booking_id = generate_booking_id()

        # Create booking (associate with specific room)
        db.execute(
            """INSERT INTO bookings 
               (booking_id, name, phone, email, room_id, sharing_type, ac_type, price, status, address, password_hash) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (booking_id, name, phone, email, room['id'], sharing_type, ac_type, price, 'Pending', address, password_hash_to_store)
        )

        new_available_beds = room['available_beds'] - 1
        new_status = 'occupied' if new_available_beds == 0 else 'available'
        db.execute(
            "UPDATE rooms SET available_beds = ?, status = ? WHERE id = ?",
            (new_available_beds, new_status, room['id'])
        )
        add_notification('public', None, f'Booking {booking_id} submitted successfully.', 'success')
        db.commit()

        flash(f'Booking successful! Your booking ID is {booking_id}. Please save this for future reference.', 'success')
        return redirect(url_for('booking.booking_success', booking_id=booking_id))

    price_table = [
        {'sharing_type': 1, 'ac_type': 'AC', 'price': 9000},
        {'sharing_type': 1, 'ac_type': 'Non-AC', 'price': 6000},
        {'sharing_type': 2, 'ac_type': 'AC', 'price': 7500},
        {'sharing_type': 2, 'ac_type': 'Non-AC', 'price': 6000},
        {'sharing_type': 3, 'ac_type': 'AC', 'price': 6500},
        {'sharing_type': 3, 'ac_type': 'Non-AC', 'price': 5500},
        {'sharing_type': 4, 'ac_type': 'AC', 'price': 6000},
        {'sharing_type': 4, 'ac_type': 'Non-AC', 'price': 5000},
    ]
    # Load rooms to display with capacities and slots (rooms are admin-managed)
    try:
        db = get_db()
        rooms = db.execute("SELECT * FROM rooms ORDER BY CAST(room_no AS INTEGER) ASC").fetchall()
    except Exception:
        # Log error for investigation and fall back to empty list to avoid 500
        import traceback
        with open('booking_error.log', 'a', encoding='utf-8') as fh:
            fh.write('--- Booking GET error:\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        rooms = []
        return render_template('book_room.html', price_table=price_table, rooms=rooms)

    # Normalize DB rows to plain dicts so templates can safely use `.get()` and index access
    try:
        rooms = [dict(r) for r in rooms] if rooms else []
    except Exception:
        # fallback: leave as-is
        pass

    # If a specific room is requested, pass it to template to show the booking form
    selected_room = None
    room_id_q = request.args.get('room_id')
    if room_id_q:
        try:
            sel = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id_q,)).fetchone()
            selected_room = dict(sel) if sel else None
        except Exception:
            selected_room = None

    # Use the exact given `price_table` values as the canonical price map
    price_map = {}
    for entry in price_table:
        price_map[(entry['sharing_type'], entry['ac_type'])] = int(entry['price'])

    # Also provide a string-keyed price map for templates (Jinja tuple keys can be awkward)
    price_map_str = { f"{st}:{ac}": price_map.get((st, ac), get_room_price(st, ac))
                      for st in (1,2,3,4) for ac in ('AC','Non-AC') }

    return render_template('book_room.html', price_table=price_table, rooms=rooms, selected_room=selected_room, price_map=price_map, price_map_str=price_map_str)
    

@booking_bp.route('/booking/success/<booking_id>')
def booking_success(booking_id):
    db = get_db()
    booking = db.execute(
        """SELECT b.*, r.room_no, r.ac_type, r.sharing_type 
           FROM bookings b 
           LEFT JOIN rooms r ON b.room_id = r.id 
           WHERE b.booking_id = ?""",
        (booking_id,)
    ).fetchone()
    
    if not booking:
        flash('Invalid booking ID', 'danger')
        return redirect(url_for('booking.book_room'))
    
    # If a receipt id was passed after payment, show download link and payment contact
    receipt_id = request.args.get('receipt_id')
    payment_phone = os.environ.get('PAYMENT_PHONE') or (booking['phone'] if booking and 'phone' in booking and booking['phone'] else '')
    payment_qr = ''
    if payment_phone:
        payment_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={quote_plus(payment_phone)}"

    return render_template('booking_success.html', booking=booking, receipt_id=receipt_id, payment_phone=payment_phone, payment_qr=payment_qr)


@booking_bp.route('/book-debug')
def book_debug():
    return 'OK'

@booking_bp.route('/rooms')
def available_rooms():
    db = get_db()
    
    # Get filter parameters
    ac_type = request.args.get('ac_type', '').strip()
    sharing_filter = request.args.get('sharing_type', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()

    query = """
        SELECT * FROM rooms
        WHERE available_beds > 0
    """
    params = []
    
    if ac_type:
        query += " AND ac_type = ?"
        params.append(ac_type)
    
    if sharing_filter:
        query += " AND sharing_type = ?"
        params.append(sharing_filter)
    
    if min_price:
        query += " AND price >= ?"
        params.append(min_price)
    
    if max_price:
        query += " AND price <= ?"
        params.append(max_price)
    
    query += " ORDER BY sharing_type, ac_type, room_no"
    
    rooms = db.execute(query, params).fetchall()
    
    # Get unique filter options
    ac_types = db.execute("SELECT DISTINCT ac_type FROM rooms ORDER BY ac_type").fetchall()
    sharing_types = db.execute("SELECT DISTINCT sharing_type FROM rooms ORDER BY sharing_type").fetchall()
    
    return render_template('rooms.html', rooms=rooms, ac_types=ac_types, sharing_types=sharing_types)


@booking_bp.route('/booking/preview')
def booking_preview():
    """Render booking preview for a specific room or selection."""
    db = get_db()
    room = None
    price = None

    room_id = request.args.get('room_id')
    sharing_type = request.args.get('sharing_type')
    ac_type = request.args.get('ac_type')

    try:
        if room_id:
            room = db.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
            if room:
                # Prefer explicit room price if present
                if room.get('price') is not None:
                    price = int(room['price'])
                else:
                    # try to derive price from another room with same config
                    cand = db.execute(
                        'SELECT price FROM rooms WHERE sharing_type = ? AND ac_type = ? AND price IS NOT NULL LIMIT 1',
                        (room['sharing_type'], room['ac_type'])
                    ).fetchone()
                    if cand and cand['price'] is not None:
                        price = int(cand['price'])

        elif sharing_type and ac_type:
            try:
                st = int(sharing_type)
            except Exception:
                st = None
            if st:
                room = db.execute(
                    'SELECT * FROM rooms WHERE sharing_type = ? AND ac_type = ? AND available_beds > 0 LIMIT 1',
                    (st, ac_type)
                ).fetchone()
                if room and room.get('price') is not None:
                    price = int(room['price'])

        # Fallbacks
        if price is None:
            if room and room.get('price') is not None:
                price = int(room['price'])
            else:
                # If we have sharing/ac values, try to derive from any matching room
                try:
                    st_val = room['sharing_type'] if room else (int(sharing_type) if sharing_type else None)
                except Exception:
                    st_val = None
                ac_val = room['ac_type'] if room else ac_type
                if st_val and ac_val:
                    cand = db.execute(
                        'SELECT price FROM rooms WHERE sharing_type = ? AND ac_type = ? AND price IS NOT NULL LIMIT 1',
                        (st_val, ac_val)
                    ).fetchone()
                    if cand and cand['price'] is not None:
                        price = int(cand['price'])
                # Final fallback to mapping function
                if price is None:
                    try:
                        price = get_room_price(int(st_val) if st_val else 2, ac_val if ac_val else 'Non-AC')
                    except Exception:
                        price = get_room_price(2, 'Non-AC')

    except Exception:
        # safe fallback
        price = get_room_price(2, 'Non-AC')

    if not room:
        flash('Requested room not available', 'warning')
        return redirect(url_for('booking.available_rooms'))

    # Normalize row to dict for template compatibility (templates sometimes call .get())
    try:
        room = dict(room) if room else None
    except Exception:
        pass

    return render_template('booking_preview.html', room=room, price=price)

@booking_bp.route('/admin/bookings')
def admin_bookings():
    if 'admin' not in session:
        flash('Please login as admin', 'danger')
        return redirect(url_for('auth.admin_login'))
    # cleanup rejected bookings older than 24 hours
    cleanup_old_rejected()

    db = get_db()
    bookings = db.execute(
        """SELECT b.*, r.room_no 
           FROM bookings b 
           LEFT JOIN rooms r ON b.room_id = r.id 
           ORDER BY b.created_at DESC"""
    ).fetchall()
    
    return render_template('admin_bookings.html', bookings=bookings)


def cleanup_old_rejected():
    """Delete bookings with status 'Rejected' older than 24 hours along with related payments."""
    db = get_db()
    try:
        # find bookings older than 24 hours
        rows = db.execute(
            "SELECT id FROM bookings WHERE status = 'Rejected' AND datetime(created_at) <= datetime('now', '-5 minutes')"
        ).fetchall()
        ids = [r['id'] for r in rows]
        if not ids:
            return
        # delete related payments
        q_marks = ','.join(['?'] * len(ids))
        db.execute(f"DELETE FROM payments WHERE booking_id IN ({q_marks})", tuple(ids))
        # delete bookings
        db.execute(f"DELETE FROM bookings WHERE id IN ({q_marks})", tuple(ids))
        db.commit()
    except Exception:
        # don't raise; log to file for inspection
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- cleanup_old_rejected error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')


@booking_bp.route('/admin/booking/<int:booking_id>')
def admin_booking_detail(booking_id):
    if 'admin' not in session:
        flash('Please login as admin', 'danger')
        return redirect(url_for('auth.admin_login'))

    db = get_db()
    booking = db.execute(
        """SELECT b.*, r.room_no FROM bookings b LEFT JOIN rooms r ON b.room_id = r.id WHERE b.id = ?""",
        (booking_id,),
    ).fetchone()

    if not booking:
        flash('Booking not found', 'danger')
        return redirect(url_for('booking.admin_bookings'))

    # Compute payment status for this booking
    payments = db.execute('SELECT amount, status FROM payments WHERE booking_id = ?', (booking_id,)).fetchall()
    total_paid = sum(p['amount'] for p in payments if p['status'] == 'Paid') if payments else 0
    price = booking['price'] or 0
    if total_paid >= price and price > 0:
        payment_status = 'Full Paid'
    elif total_paid > 0 and total_paid < price:
        payment_status = 'Half Paid'
    else:
        payment_status = 'Not Paid'

    return render_template('admin_booking_detail.html', booking=booking, payment_status=payment_status, total_paid=total_paid)


@booking_bp.route('/admin/booking/<int:booking_id>/action', methods=['POST'])
def admin_booking_action(booking_id):
    if 'admin' not in session:
        flash('Please login as admin', 'danger')
        return redirect(url_for('auth.admin_login'))
    try:
        action = request.form.get('action')  # 'accept' or 'reject'
        db = get_db()
        booking = db.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('booking.admin_bookings'))

        # Determine payment totals
        payments = db.execute('SELECT amount, status FROM payments WHERE booking_id = ?', (booking_id,)).fetchall()
        total_paid = sum(p['amount'] for p in payments if p['status'] == 'Paid') if payments else 0
        price = booking['price'] or 0
        if total_paid >= price and price > 0:
            payment_status = 'Full Paid'
        elif total_paid > 0 and total_paid < price:
            payment_status = 'Half Paid'
        else:
            payment_status = 'Not Paid'

        if action == 'accept':
            # Update room occupancy
            room = db.execute('SELECT * FROM rooms WHERE id = ?', (booking['room_id'],)).fetchone()
            if room:
                db.execute(
                    """
                    UPDATE rooms
                    SET occupied = occupied + 1,
                        available_beds = CASE WHEN total_beds - (occupied + 1) < 0 THEN 0 ELSE total_beds - (occupied + 1) END,
                        status = CASE WHEN total_beds - (occupied + 1) <= 0 THEN 'occupied' ELSE 'available' END
                    WHERE id = ?
                    """,
                    (booking['room_id'],),
                )

            user, temp_password = ensure_booking_user(booking, verified=True)
            try:
                add_notification('student', user['id'], f'Your booking {booking["booking_id"]} has been approved.', 'success')
            except Exception:
                pass
            email_html = (
                f"<h3>Booking Approved</h3>"
                f"<p>Dear {booking['name']}, your booking {booking['booking_id']} has been approved by admin.</p>"
                f"<p>You can now log in with your email address.</p>"
            )
            if temp_password:
                email_html += f"<p>Temporary password: <strong>{temp_password}</strong></p>"
            try:
                send_email(booking['email'], 'Booking Confirmation', email_html)
            except Exception:
                pass

            db.execute('UPDATE bookings SET status = ? WHERE id = ?', ('Confirmed', booking_id))
            db.commit()
            flash('Booking accepted and resident approved.', 'success')

        elif action == 'reject':
            # Reject booking: free room slot
            room = db.execute('SELECT * FROM rooms WHERE id = ?', (booking['room_id'],)).fetchone()
            if room:
                db.execute(
                    """
                    UPDATE rooms
                    SET available_beds = CASE WHEN available_beds + 1 > total_beds THEN total_beds ELSE available_beds + 1 END,
                        status = 'available'
                    WHERE id = ?
                    """,
                    (booking['room_id'],),
                )
            db.execute('UPDATE bookings SET status = ? WHERE id = ?', ('Rejected', booking_id))
            db.commit()
            try:
                add_notification('public', None, f'Booking {booking["booking_id"]} was rejected.', 'danger')
            except Exception:
                pass
            # send rejection email to user
            try:
                email_html = (
                    f"<h3>Booking Rejected</h3>"
                    f"<p>Dear {booking['name']}, your booking {booking['booking_id']} has been rejected by the admin.</p>"
                    f"<p>If you have questions, please contact support.</p>"
                )
                send_email(booking['email'], 'Booking Rejected', email_html)
            except Exception:
                pass

            flash('Booking rejected.', 'info')

        return redirect(url_for('booking.admin_bookings'))
    except Exception:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write(f"\n--- Exception in admin_booking_action (booking_id={booking_id}) ---\n")
            fh.write(traceback.format_exc())
            fh.write('\n')
        flash('An internal error occurred and was logged.', 'danger')
        return redirect(url_for('booking.admin_bookings'))

@booking_bp.route('/admin/booking/<int:booking_id>/update', methods=['POST'])
def update_booking_status(booking_id):
    if 'admin' not in session:
        flash('Please login as admin', 'danger')
        return redirect(url_for('auth.admin_login'))
    
    db = get_db()
    status = request.form.get('status')
    
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if not booking:
        flash('Booking not found', 'danger')
        return redirect(url_for('booking.admin_bookings'))
    
    old_status = booking['status']
    if status == 'Confirmed' and booking['status'] != 'Confirmed':
        room = db.execute("SELECT * FROM rooms WHERE id = ?", (booking['room_id'],)).fetchone()
        if room:
            db.execute(
                """
                UPDATE rooms
                SET occupied = occupied + 1,
                    available_beds = MAX(0, total_beds - (occupied + 1)),
                    status = CASE WHEN MAX(0, total_beds - (occupied + 1)) <= 0 THEN 'occupied' ELSE 'available' END
                WHERE id = ?
                """,
                (booking['room_id'],),
            )
        # Ensure student account exists and mark as approved so they can login
        user, temp_password = ensure_booking_user(booking, verified=True)
        add_notification('student', user['id'], f'Your booking {booking["booking_id"]} has been confirmed and approved.', 'success')
        email_html = (
            f"<h3>Booking Confirmed</h3>"
            f"<p>Dear {booking['name']}, your booking {booking['booking_id']} has been confirmed.</p>"
            f"<p>You can now log in with your email address.</p>"
        )
        if temp_password:
            email_html += f"<p>Temporary password: <strong>{temp_password}</strong></p>"
        send_email(booking['email'], 'Booking Confirmation', email_html)

    elif status == 'Rejected' and booking['status'] != 'Rejected':
        room = db.execute("SELECT * FROM rooms WHERE id = ?", (booking['room_id'],)).fetchone()
        if room:
            db.execute(
                """
                UPDATE rooms
                SET available_beds = MIN(total_beds, available_beds + 1),
                    status = 'available'
                WHERE id = ?
                """,
                (booking['room_id'],),
            )
        add_notification('public', None, f'Booking {booking["booking_id"]} was rejected.', 'danger')
        # send rejection email to user
        try:
            email_html = (
                f"<h3>Booking Rejected</h3>"
                f"<p>Dear {booking['name']}, your booking {booking['booking_id']} has been rejected by the admin.</p>"
                f"<p>If you have questions, please contact support.</p>"
            )
            send_email(booking['email'], 'Booking Rejected', email_html)
        except Exception:
            pass

    elif old_status == 'Rejected' and status in ('Pending', 'Approved'):
        db.execute(
            """
            UPDATE rooms
                SET available_beds = MAX(0, available_beds - 1),
                status = CASE WHEN MAX(0, available_beds - 1) <= 0 THEN 'occupied' ELSE 'available' END
            WHERE id = ?
            """,
            (booking['room_id'],),
        )

    db.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
    db.commit()
    
    flash(f'Booking status updated to {status}', 'success')
    return redirect(url_for('booking.admin_bookings'))
