from flask import Blueprint, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from hostel_pg_management.database.db import get_db
from hostel_pg_management.models.models import Room
from hostel_pg_management.routes.booking import ensure_booking_user, add_notification
from hostel_pg_management.utils.mail import send_email
from hostel_pg_management.utils.sms import send_sms

admin_bp = Blueprint('admin', __name__)


PRICE_MAP = {
    (1, 'AC'): 9000,
    (1, 'Non-AC'): 6000,
    (2, 'AC'): 7500,
    (2, 'Non-AC'): 6000,
    (3, 'AC'): 6500,
    (3, 'Non-AC'): 5500,
    (4, 'AC'): 6000,
    (4, 'Non-AC'): 5000,
}


@admin_bp.before_request
def require_admin():
    # Allow some admin pages to be viewable by students (GET only)
    public_get = {'admin.food_menu', 'admin.facilities', 'admin.complaints', 'notice.notice_board'}
    try:
        endpoint = request.endpoint or ''
    except Exception:
        endpoint = ''

    if request.method == 'GET' and endpoint in public_get:
        # allow student view (read-only) without admin session
        return None

    if 'admin' not in session:
        flash('Please log in as an administrator.', 'warning')
        return redirect('/admin_login')


@admin_bp.route('/dashboard')
def dashboard():
    db = get_db()
    # Resolve canonical room metrics from the `rooms` table
    occupancy_totals = db.execute('SELECT SUM(total_beds) as total_capacity, SUM(occupied) as total_occupied FROM rooms').fetchone()
    total_capacity = occupancy_totals['total_capacity'] or 0
    total_occupied = occupancy_totals['total_occupied'] or 0
    # Number of rooms (single source of truth)
    total_rooms = db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0] or 0
    students_count = db.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    payments_count = db.execute('SELECT COUNT(*) FROM payments').fetchone()[0]
    complaints_count = db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'").fetchone()[0]
    # Pending rooms: rooms with status 'Pending' (if any)
    pending_rooms_count = db.execute("SELECT COUNT(*) FROM rooms WHERE status = 'Pending'").fetchone()[0]
    resolved_complaints_count = db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'").fetchone()[0]
    in_progress_count = db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'").fetchone()[0]

    total_revenue = db.execute("SELECT SUM(amount + COALESCE(late_fee, 0)) FROM payments WHERE status = 'Paid'").fetchone()[0] or 0
    available_rooms = db.execute('SELECT COUNT(*) FROM rooms WHERE available_beds > 0').fetchone()[0]
    occupied_rooms = db.execute('SELECT COUNT(DISTINCT room_id) FROM students WHERE room_id IS NOT NULL').fetchone()[0]
    available_seats = max(0, total_capacity - total_occupied)
    pending_revenue = max(0, (students_count * 5000) - total_revenue)

    monthly_revenue = db.execute(
        '''
        SELECT strftime('%Y-%m', payment_date) as month, SUM(amount + COALESCE(late_fee, 0)) as total
        FROM payments
        WHERE status = 'Paid'
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        '''
    ).fetchall()
    monthly_labels = [row['month'] for row in monthly_revenue[::-1]]
    monthly_amounts = [row['total'] for row in monthly_revenue[::-1]]

    # Fetch all rooms to show on admin dashboard for quick controls
    # Use the same ordering and canonical source as the booking module
    rooms_list = db.execute('SELECT * FROM rooms ORDER BY CAST(room_no AS INTEGER) ASC').fetchall()
    # Normalize sqlite3.Row -> dict so templates can safely use .get() and JSON responses
    try:
        rooms_list = [dict(r) for r in rooms_list] if rooms_list else []
    except Exception:
        # fallback: leave as-is to avoid breaking the page
        pass

    return render_template(
        'admin_dashboard.html',
        rooms_count=total_rooms,
        students_count=students_count,
        payments_count=payments_count,
        complaints_count=complaints_count,
        pending_rooms_count=pending_rooms_count,
        resolved_complaints_count=resolved_complaints_count,
        in_progress_count=in_progress_count,
        total_revenue=total_revenue,
        pending_revenue=pending_revenue,
        available_rooms=available_rooms,
        occupied_rooms=occupied_rooms,
        total_capacity=total_capacity,
        total_occupied=total_occupied,
        available_seats=available_seats,
        monthly_labels=monthly_labels,
        monthly_amounts=monthly_amounts,
        rooms=rooms_list,
    )


@admin_bp.route('/api/update_room/<int:room_id>', methods=['POST'])
def api_update_room(room_id):
    """AJAX endpoint: update room details and return JSON."""
    db = get_db()
    try:
        sharing_type = int(request.form.get('sharing_type') or 1)
        ac_type = request.form.get('ac_type') or 'Non-AC'
        price = int(request.form.get('price') or 0)
        category = request.form.get('category') or 'Comfort'

        total_beds = sharing_type
        db.execute(
            '''
            UPDATE rooms
            SET sharing_type=?, ac_type=?, total_beds=?, price=?, category=?, available_beds = CASE WHEN ? - occupied < 0 THEN 0 ELSE ? - occupied END,
                status = CASE WHEN (? - occupied) <= 0 THEN 'occupied' ELSE 'available' END
            WHERE id=?
            ''',
            (sharing_type, ac_type, total_beds, price, category, total_beds, total_beds, total_beds, room_id),
        )
        # Keep bookings in sync for this room: update stored sharing_type, ac_type and price
        try:
            db.execute('UPDATE bookings SET sharing_type=?, ac_type=?, price=? WHERE room_id=?', (sharing_type, ac_type, price, room_id))
        except Exception:
            # non-fatal: continue but log
            import traceback
            with open('server_errors.log', 'a', encoding='utf-8') as fh:
                fh.write('\n--- admin.api_update_room bookings sync error ---\n')
                fh.write(traceback.format_exc())
                fh.write('\n')
        db.commit()
        row = db.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
        if not row:
            return ({'success': False, 'error': 'Room not found'}, 404)
        return ({'success': True, 'room': dict(row)}, 200)
    except Exception as e:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- admin.api_update_room error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        return ({'success': False, 'error': str(e)}, 500)


@admin_bp.route('/api/delete_room/<int:room_id>', methods=['POST'])
def api_delete_room(room_id):
    db = get_db()
    room = db.execute('SELECT occupied FROM rooms WHERE id=?', (room_id,)).fetchone()
    if room and room['occupied'] > 0:
        return ({'success': False, 'error': 'Cannot delete room with assigned residents.'}, 400)
    try:
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        db.commit()
        return ({'success': True}, 200)
    except Exception as e:
        return ({'success': False, 'error': str(e)}, 500)


@admin_bp.route('/rooms', methods=['GET', 'POST'])
def rooms():
    db = get_db()
    if request.method == 'POST':
        room_no = request.form.get('room_no')
        sharing_type = int(request.form.get('sharing_type') or 1)
        ac_type = request.form.get('ac_type') or 'Non-AC'
        category = request.form.get('category') or 'Comfort'
        total_beds = sharing_type
        price = PRICE_MAP.get((sharing_type, ac_type), 5000)

        existing = db.execute('SELECT * FROM rooms WHERE room_no = ?', (room_no,)).fetchone()
        if existing:
            flash(f'Room {room_no} already exists!', 'danger')
        else:
            db.execute(
                '''
                INSERT INTO rooms (room_no, sharing_type, ac_type, total_beds, available_beds, price, status, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (room_no, sharing_type, ac_type, total_beds, total_beds, price, 'available', category),
            )
            db.commit()
            flash('Room added successfully.', 'success')
        return redirect('/admin/rooms')

    # Use booking module ordering and normalize rows to dicts
    rooms_list = db.execute('SELECT * FROM rooms ORDER BY CAST(room_no AS INTEGER) ASC').fetchall()
    try:
        rooms_list = [dict(r) for r in rooms_list] if rooms_list else []
    except Exception:
        pass
    return render_template('rooms.html', rooms=rooms_list, filters={})


@admin_bp.route('/rooms/seed', methods=['POST'])
def seed_rooms():
    """Admin-only: create rooms 1..300 if missing. Idempotent."""
    db = get_db()
    try:
        created = 0
        for i in range(1, 301):
            rn = str(i)
            existing = db.execute('SELECT id FROM rooms WHERE room_no = ?', (rn,)).fetchone()
            if existing:
                continue
            sharing_type_default = ((i - 1) % 3) + 1
            ac_type_default = 'AC' if (i % 2 == 0) else 'Non-AC'
            price_default = PRICE_MAP.get((sharing_type_default, ac_type_default), 5000)
            category_default = 'Prime' if ac_type_default == 'AC' else 'Comfort'
            db.execute(
                'INSERT INTO rooms (room_no, sharing_type, ac_type, total_beds, available_beds, price, status, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (rn, sharing_type_default, ac_type_default, sharing_type_default, sharing_type_default, price_default, 'available', category_default)
            )
            created += 1
        if created:
            db.commit()
            flash(f'Created {created} rooms (missing ones).', 'success')
        else:
            flash('No new rooms needed; all 1..300 already exist.', 'info')
    except Exception:
        flash('Failed to seed rooms. Check server logs.', 'danger')
    return redirect('/admin/rooms')


@admin_bp.route('/edit_room/<int:room_id>', methods=['POST'])
def edit_room(room_id):
    db = get_db()
    sharing_type = int(request.form.get('sharing_type') or 1)
    ac_type = request.form.get('ac_type') or 'Non-AC'
    price = int(request.form.get('price') or 0)
    category = request.form.get('category') or 'Comfort'

    # Update total_beds based on sharing_type
    total_beds = sharing_type
    try:
        # adjust occupied/available safely
        db.execute(
            '''
            UPDATE rooms
            SET sharing_type=?, ac_type=?, total_beds=?, price=?, category=?, available_beds = CASE WHEN ? - occupied < 0 THEN 0 ELSE ? - occupied END,
                status = CASE WHEN (? - occupied) <= 0 THEN 'occupied' ELSE 'available' END
            WHERE id=?
            ''',
            (sharing_type, ac_type, total_beds, price, category, total_beds, total_beds, total_beds, room_id),
        )
        # Sync bookings that reference this room so their stored pricing and room metadata stay current
        try:
            db.execute('UPDATE bookings SET sharing_type=?, ac_type=?, price=? WHERE room_id=?', (sharing_type, ac_type, price, room_id))
        except Exception:
            # Log but don't block the update
            import traceback
            with open('server_errors.log', 'a', encoding='utf-8') as fh:
                fh.write('\n--- admin.edit_room bookings sync error ---\n')
                fh.write(traceback.format_exc())
                fh.write('\n')
        db.commit()
        flash('Room updated successfully.', 'success')
    except Exception:
        flash('Failed to update room.', 'danger')
    return redirect('/admin/rooms')


@admin_bp.route('/food_menu', methods=['GET', 'POST'])
def food_menu():
    db = get_db()
    if request.method == 'POST':
        # Expect fields like breakfast_1 ... breakfast_7 etc.
        try:
            for idx, day in enumerate(['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'], start=1):
                b = request.form.get(f'breakfast_{idx}') or ''
                l = request.form.get(f'lunch_{idx}') or ''
                d = request.form.get(f'dinner_{idx}') or ''
                # update existing row by ordering
                db.execute('UPDATE food_menu SET breakfast=?, lunch=?, dinner=? WHERE id = (SELECT id FROM food_menu ORDER BY id LIMIT 1 OFFSET ?)', (b, l, d, idx-1))
            db.commit()
            flash('Food menu updated.', 'success')
        except Exception:
            flash('Failed to update food menu.', 'danger')
        return redirect('/admin/food_menu')

    try:
        menu = db.execute('SELECT id, day, breakfast, lunch, dinner FROM food_menu ORDER BY id').fetchall()
    except Exception as e:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- admin.food_menu DB error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        flash(f'Database error while loading food menu: {e}', 'danger')
        menu = []
    # If a student is viewing, render a read-only student view
    if session.get('student_id') and request.method == 'GET':
        return render_template('student_food_menu.html', menu=menu)

    return render_template('admin_food_menu.html', menu=menu)


@admin_bp.route('/facilities', methods=['GET', 'POST'])
def facilities():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        if not name:
            flash('Name required', 'danger')
            return redirect('/admin/facilities')
        try:
            db.execute('INSERT INTO facilities (name, description) VALUES (?, ?)', (name, description))
            db.commit()
            flash('Facility added.', 'success')
        except Exception:
            flash('Failed to add facility.', 'danger')
        return redirect('/admin/facilities')

    try:
        facs = db.execute('SELECT * FROM facilities ORDER BY id').fetchall()
    except Exception as e:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- admin.facilities DB error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        flash(f'Database error while loading facilities: {e}', 'danger')
        facs = []
    # Student-facing read-only view
    if session.get('student_id') and request.method == 'GET':
        return render_template('student_facilities.html', facilities=facs)

    return render_template('admin_facilities.html', facilities=facs)


@admin_bp.route('/delete_facility/<int:fac_id>', methods=['POST'])
def delete_facility(fac_id):
    db = get_db()
    try:
        db.execute('DELETE FROM facilities WHERE id=?', (fac_id,))
        db.commit()
        flash('Facility removed.', 'success')
    except Exception:
        flash('Failed to remove facility.', 'danger')
    return redirect('/admin/facilities')


@admin_bp.route('/delete_room/<int:room_id>', methods=['POST'])
def delete_room(room_id):
    db = get_db()
    room = db.execute('SELECT occupied FROM rooms WHERE id=?', (room_id,)).fetchone()
    if room and room['occupied'] > 0:
        flash('Cannot delete room with assigned residents. Please remove residents first.', 'danger')
        return redirect('/admin/rooms')

    db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
    db.commit()
    flash('Room deleted.', 'success')
    return redirect('/admin/rooms')


@admin_bp.route('/rooms/cleanup_sample', methods=['GET', 'POST'])
def cleanup_sample_rooms():
    """Admin-only: list and optionally remove seeded/sample rooms that are empty.

    GET: show candidate rooms (occupied == 0 and matching known sample room numbers).
    POST: delete selected room ids (only if empty) and redirect to admin rooms.
    """
    db = get_db()
    # The original seeded sample room numbers used by older versions
    sample_room_nos = [
        '101','102','103','104', '201','202','203','204', '301','302','303','304', '401','402','403','404'
    ]

    if request.method == 'POST':
        ids = request.form.getlist('room_id')
        deleted = 0
        try:
            for rid in ids:
                # ensure room exists and is empty before deleting
                row = db.execute('SELECT id, occupied FROM rooms WHERE id=?', (rid,)).fetchone()
                if not row:
                    continue
                if row['occupied'] and row['occupied'] > 0:
                    continue
                db.execute('DELETE FROM rooms WHERE id=?', (rid,))
                deleted += 1
            if deleted:
                db.commit()
                flash(f'Deleted {deleted} sample rooms.', 'success')
            else:
                flash('No eligible rooms were deleted (they may be occupied or already removed).', 'info')
        except Exception:
            flash('Failed to delete selected rooms. Check server logs.', 'danger')
        return redirect('/admin/rooms')

    # GET: show candidate rooms (only those from the original sample list and empty)
    placeholder = ','.join('?' for _ in sample_room_nos)
    query = f"SELECT * FROM rooms WHERE room_no IN ({placeholder}) AND (occupied IS NULL OR occupied = 0) ORDER BY CAST(room_no AS INTEGER) ASC"
    candidates = db.execute(query, tuple(sample_room_nos)).fetchall()
    try:
        candidates = [dict(r) for r in candidates] if candidates else []
    except Exception:
        pass
    return render_template('admin_cleanup_rooms.html', candidates=candidates)


@admin_bp.route('/students', methods=['GET', 'POST'])
def students():
    db = get_db()
    # Manual adding of users via admin UI is disabled per policy.
    if request.method == 'POST':
        flash('Manual user creation is disabled. Users are created when bookings are accepted.', 'warning')
        return redirect('/admin/students')

    search_q = request.args.get('search', '')
    query = '''
        SELECT DISTINCT students.id, students.name, students.email, students.phone, students.room_id,
               rooms.room_no, rooms.total_beds, rooms.ac_type, rooms.occupied, students.id_proof, students.is_verified
        FROM students
        LEFT JOIN rooms ON students.room_id = rooms.id
        WHERE EXISTS (
            SELECT 1 FROM bookings b WHERE LOWER(b.email) = LOWER(students.email) AND b.status = 'Confirmed'
        )
    '''
    params = []
    if search_q:
        query += ' AND (students.name LIKE ? OR students.email LIKE ?)'
        params.extend([f'%{search_q}%', f'%{search_q}%'])

    students_list = db.execute(query, params).fetchall()
    rooms_list = Room.get_available()
    # canonical all_rooms ordering
    all_rooms = db.execute('SELECT * FROM rooms ORDER BY CAST(room_no AS INTEGER) ASC').fetchall()
    try:
        all_rooms = [dict(r) for r in all_rooms] if all_rooms else []
    except Exception:
        pass
    return render_template('students.html', students=students_list, rooms=rooms_list, all_rooms=all_rooms, search_q=search_q)


@admin_bp.route('/verify_payment/<int:payment_id>', methods=['POST'])
def verify_payment(payment_id):
    db = get_db()
    payment = db.execute('SELECT * FROM payments WHERE id=?', (payment_id,)).fetchone()
    if not payment:
        flash('Payment record not found.', 'danger')
        return redirect('/admin/payments')
    try:
        db.execute('UPDATE payments SET status=? WHERE id=?', ('Paid', payment_id))
        db.commit()
        flash('Payment verified and marked as Paid.', 'success')
    except Exception:
        flash('Failed to verify payment.', 'danger')
    # After verifying payment, if this payment belongs to a booking, check total paid and auto-accept if half or more
    try:
        booking_id = payment.get('booking_id') if isinstance(payment, dict) else payment['booking_id']
        if booking_id:
            booking = db.execute('SELECT * FROM bookings WHERE id=?', (booking_id,)).fetchone()
            if booking and booking['status'] != 'Confirmed':
                total_paid = db.execute('SELECT SUM(amount) as total FROM payments WHERE booking_id=? AND status="Paid"', (booking_id,)).fetchone()['total'] or 0
                price = booking['price'] or 0
                # Auto-accept when total_paid >= 50% of price
                if price > 0 and total_paid >= (price / 2):
                    # update room occupancy
                    if booking['room_id']:
                        Room.update_occupancy(booking['room_id'], increment=True)

                    user, temp_password = ensure_booking_user(booking, verified=True)
                    try:
                        add_notification('student', user['id'], f'Your booking {booking["booking_id"]} has been confirmed.', 'success')
                    except Exception:
                        pass
                    email_html = (
                        f"<h3>Booking Confirmed</h3>"
                        f"<p>Dear {booking['name']}, your booking {booking['booking_id']} has been confirmed.</p>"
                        f"<p>You can now log in with your email address.</p>"
                    )
                    if temp_password:
                        email_html += f"<p>Temporary password: <strong>{temp_password}</strong></p>"
                    try:
                        send_email(booking['email'], 'Booking Confirmed', email_html)
                    except Exception:
                        pass
                    db.execute('UPDATE bookings SET status=? WHERE id=?', ('Confirmed', booking_id))
                    db.commit()
    except Exception:
        # don't break flow; log and continue
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- verify_payment post-process error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
    return redirect('/admin/payments')


@admin_bp.route('/verify_resident/<int:student_id>', methods=['POST'])
def verify_resident(student_id):
    db = get_db()
    db.execute('UPDATE students SET is_verified=1 WHERE id=?', (student_id,))
    db.execute(
        '''
        INSERT INTO id_verifications (student_id, id_proof_path, verification_status, verified_by, verified_at)
        SELECT id, id_proof, 'Verified', 1, CURRENT_TIMESTAMP
        FROM students WHERE id=?
        ''',
        (student_id,),
    )
    db.commit()
    flash('Aadhar verified successfully.', 'success')
    return redirect('/admin/students')


@admin_bp.route('/reject_resident/<int:student_id>', methods=['POST'])
def reject_resident(student_id):
    db = get_db()
    db.execute('UPDATE students SET id_proof=NULL, is_verified=0 WHERE id=?', (student_id,))
    db.execute(
        '''
        INSERT INTO id_verifications (student_id, verification_status, verified_by, verified_at, remarks)
        VALUES (?, 'Rejected', 1, CURRENT_TIMESTAMP, 'Please upload a clear Aadhar copy.')
        ''',
        (student_id,),
    )
    db.commit()
    flash('Aadhar rejected. The user must upload a new copy.', 'warning')
    return redirect('/admin/students')


@admin_bp.route('/edit_student/<int:student_id>', methods=['POST'])
def edit_student(student_id):
    db = get_db()
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    new_room_id = request.form.get('room_id') or None

    old_student = db.execute('SELECT room_id FROM students WHERE id=?', (student_id,)).fetchone()
    old_room_id = str(old_student['room_id']) if old_student and old_student['room_id'] else ''
    if old_room_id != str(new_room_id or ''):
        if new_room_id:
            room_check = db.execute('SELECT available_beds FROM rooms WHERE id=?', (new_room_id,)).fetchone()
            if room_check and room_check['available_beds'] <= 0:
                flash('Cannot assign to selected room as it is already full!', 'danger')
                return redirect('/admin/students')
        if old_room_id:
            Room.update_occupancy(old_room_id, increment=False)
        if new_room_id:
            Room.update_occupancy(new_room_id, increment=True)

    db.execute(
        'UPDATE students SET name=?, email=?, phone=?, room_id=? WHERE id=?',
        (name, email, phone, new_room_id, student_id),
    )
    db.commit()
    flash('User updated successfully.', 'success')
    return redirect('/admin/students')


@admin_bp.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    db = get_db()
    student = db.execute('SELECT room_id FROM students WHERE id=?', (student_id,)).fetchone()
    if student and student['room_id']:
        Room.update_occupancy(student['room_id'], increment=False)
    db.execute('DELETE FROM students WHERE id=?', (student_id,))
    db.commit()
    flash('User deleted successfully.', 'success')
    return redirect('/admin/students')


@admin_bp.route('/payments', methods=['GET', 'POST'])
def payments():
    db = get_db()
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        amount = request.form.get('amount')
        payment_date = request.form.get('date')
        payment_month = payment_date[:7]
        due_date = f'{payment_month}-05'
        late_fee = 0
        if payment_date > due_date:
            late_fee = (datetime.strptime(payment_date, '%Y-%m-%d').date() - datetime.strptime(due_date, '%Y-%m-%d').date()).days * 50

        db.execute(
            '''
            INSERT INTO payments (student_id, amount, payment_month, payment_date, due_date, status, late_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (student_id, amount, payment_month, payment_date, due_date, 'Paid', late_fee),
        )
        db.commit()
        flash('Payment recorded.', 'success')
        return redirect('/admin/payments')

    try:
        payments_list = db.execute(
        '''
        SELECT p.id, s.name, p.amount, p.payment_date, p.payment_month, p.due_date, p.status, p.late_fee
        FROM payments p JOIN students s ON p.student_id = s.id
        ORDER BY p.id DESC
        '''
    ).fetchall()
        students_list = db.execute('SELECT id, name FROM students').fetchall()
    except Exception as e:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- admin.payments DB error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        flash(f'Database error while loading payments: {e}', 'danger')
        payments_list = []
        students_list = []
    return render_template('payments.html', payments=payments_list, students=students_list)


@admin_bp.route('/delete_payment/<int:payment_id>', methods=['POST'])
def delete_payment(payment_id):
    db = get_db()
    db.execute('DELETE FROM payments WHERE id=?', (payment_id,))
    db.commit()
    flash('Payment deleted.', 'success')
    return redirect('/admin/payments')


@admin_bp.route('/complaints')
def complaints():
    db = get_db()
    status_filter = request.args.get('status')
    query = '''
        SELECT c.id, s.name, c.subject, c.complaint, c.status, c.created_at
        FROM complaints c JOIN students s ON c.student_id = s.id
    '''
    params = []
    # By default exclude solved/resolved complaints from admin listing (so admin dashboard focuses on actionable items)
    if status_filter:
        query += ' WHERE c.status = ?'
        params.append(status_filter)
    else:
        query += " WHERE c.status NOT IN ('Resolved','Solved')"
    query += ' ORDER BY c.created_at DESC'
    try:
        complaints_list = db.execute(query, params).fetchall()
        # fetch reply counts
        reply_rows = db.execute('SELECT complaint_id, COUNT(*) as cnt FROM complaint_replies GROUP BY complaint_id').fetchall()
        reply_counts = {r['complaint_id']: r['cnt'] for r in reply_rows}
    except Exception as e:
        import traceback
        with open('server_errors.log', 'a', encoding='utf-8') as fh:
            fh.write('\n--- admin.complaints DB error ---\n')
            fh.write(traceback.format_exc())
            fh.write('\n')
        flash(f'Database error while loading complaints: {e}', 'danger')
        complaints_list = []
        reply_counts = {}
    # If a student clicked Help/Support, the section is removed per requirements — show a minimal message
    if session.get('student_id') and request.method == 'GET':
        return render_template('help_removed.html')

    return render_template('admin_complaints.html', complaints=complaints_list, current_filter=status_filter, reply_counts=reply_counts)



@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    db = get_db()
    if request.method == 'POST':
        emergency = request.form.get('emergency_number')
        try:
            cur = db.execute("SELECT value FROM settings WHERE key='emergency_number'").fetchone()
            if cur:
                db.execute("UPDATE settings SET value=? WHERE key='emergency_number'", (emergency,))
            else:
                db.execute("INSERT INTO settings (key, value) VALUES ('emergency_number', ?)", (emergency,))
            db.commit()
            flash('Settings updated.', 'success')
        except Exception:
            flash('Failed to update settings.', 'danger')
        return redirect('/admin/complaints')

    row = db.execute("SELECT value FROM settings WHERE key='emergency_number'").fetchone()
    emergency_number = row['value'] if row else '+91 98765 40000'
    return render_template('admin_settings.html', emergency_number=emergency_number)


@admin_bp.route('/update_complaint/<int:id>', methods=['POST'])
def update_complaint(id):
    new_status = request.form.get('status')
    db = get_db()
    db.execute('UPDATE complaints SET status=? WHERE id=?', (new_status, id))
    db.commit()
    flash(f'Complaint status updated to {new_status}.', 'success')
    return redirect('/admin/complaints')


@admin_bp.route('/reply_complaint/<int:complaint_id>', methods=['POST'])
def reply_complaint(complaint_id):
    db = get_db()
    reply = request.form.get('reply')
    if not reply:
        flash('Reply message cannot be empty.', 'danger')
        return redirect('/admin/complaints')
    try:
        # admin_id from session if available
        admin_id = None
        if session.get('admin'):
            # attempt to fetch admin id
            admin_user = session.get('admin_username')
            if admin_user:
                admin_rec = db.execute('SELECT id FROM admin WHERE username=?', (admin_user,)).fetchone()
                admin_id = admin_rec['id'] if admin_rec else None

        db.execute('INSERT INTO complaint_replies (complaint_id, admin_id, message) VALUES (?, ?, ?)', (complaint_id, admin_id, reply))
        db.commit()
        # notify student via email
        student = db.execute('SELECT s.email, s.name, c.subject FROM complaints c JOIN students s ON c.student_id = s.id WHERE c.id=?', (complaint_id,)).fetchone()
        if student:
            email_html = f"<h3>Response to your complaint: {student['subject']}</h3><p>Dear {student['name']},</p><p>{reply}</p>"
            try:
                send_email(student['email'], f"Response: {student['subject']}", email_html)
            except Exception:
                pass
        flash('Reply sent to the resident and recorded.', 'success')
    except Exception:
        flash('Failed to send reply.', 'danger')
    return redirect('/admin/complaints')


@admin_bp.route('/accept_visit/<int:visit_id>', methods=['POST'])
def accept_visit(visit_id):
    db = get_db()
    visit = db.execute('SELECT * FROM visits WHERE id=?', (visit_id,)).fetchone()
    if not visit:
        flash('Visit request not found.', 'danger')
        return redirect('/admin/visits')
    try:
        db.execute("UPDATE visits SET status='Accepted' WHERE id=?", (visit_id,))
        db.commit()
        # send email/notification to visitor
        try:
            # include who the visit was for if available
            student_info = None
            if visit and 'student_id' in visit.keys() and visit['student_id']:
                student_info = db.execute('SELECT s.name as student_name, r.room_no FROM students s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id=?', (visit['student_id'],)).fetchone()
            student_text = f" for {student_info['student_name']} (Room {student_info['room_no']})" if student_info else ''
            send_email(visit['email'], 'Visit Accepted', f"<p>Dear {visit['name']}, your visit on {visit['visit_date']} at {visit['visit_time']}{student_text} has been accepted.</p>")
        except Exception:
            pass
        # send SMS to visitor
        try:
            sms_msg = f"Your visit on {visit['visit_date']} at {visit['visit_time']} has been Accepted.\n- {visit['name']}"
            send_sms(visit['phone'], sms_msg)
        except Exception:
            pass
        # notify student (if visit linked to a student_id)
        try:
            sid = visit['student_id'] if 'student_id' in visit.keys() and visit['student_id'] else None
            if sid:
                add_notification('student', sid, f"Your visitor ({visit.get('relation','')}) visit has been Approved", 'success')
                db.commit()
        except Exception:
            pass
        flash('Visit accepted.', 'success')
    except Exception:
        flash('Failed to accept visit.', 'danger')
    return redirect('/admin/visits')


@admin_bp.route('/reject_visit/<int:visit_id>', methods=['POST'])
def reject_visit(visit_id):
    db = get_db()
    visit = db.execute('SELECT * FROM visits WHERE id=?', (visit_id,)).fetchone()
    if not visit:
        flash('Visit request not found.', 'danger')
        return redirect('/admin/visits')
    try:
        db.execute("UPDATE visits SET status='Rejected' WHERE id=?", (visit_id,))
        db.commit()
        try:
            student_info = None
            if visit and 'student_id' in visit.keys() and visit['student_id']:
                student_info = db.execute('SELECT s.name as student_name, r.room_no FROM students s LEFT JOIN rooms r ON s.room_id = r.id WHERE s.id=?', (visit['student_id'],)).fetchone()
            student_text = f" for {student_info['student_name']} (Room {student_info['room_no']})" if student_info else ''
            send_email(visit['email'], 'Visit Request Rejected', f"<p>Dear {visit['name']}, your visit request for {visit['visit_date']} at {visit['visit_time']}{student_text} has been rejected.</p>")
        except Exception:
            pass
        try:
            sms_msg = f"Your visit on {visit['visit_date']} at {visit['visit_time']} has been Rejected.\n- {visit['name']}"
            send_sms(visit['phone'], sms_msg)
        except Exception:
            pass
        try:
            sid = visit['student_id'] if 'student_id' in visit.keys() and visit['student_id'] else None
            if sid:
                add_notification('student', sid, f"Your visitor ({visit.get('relation','')}) visit has been Rejected", 'warning')
                db.commit()
        except Exception:
            pass
        flash('Visit rejected.', 'warning')
    except Exception:
        flash('Failed to reject visit.', 'danger')
    return redirect('/admin/visits')


@admin_bp.route('/delete_visit/<int:visit_id>', methods=['POST'])
def delete_visit(visit_id):
    db = get_db()
    visit = db.execute('SELECT * FROM visits WHERE id=?', (visit_id,)).fetchone()
    if not visit:
        flash('Visit request not found.', 'danger')
        return redirect('/admin/visits')
    try:
        db.execute('DELETE FROM visits WHERE id=?', (visit_id,))
        db.commit()
        flash('Visit request deleted.', 'success')
    except Exception:
        flash('Failed to delete visit request.', 'danger')
    return redirect('/admin/visits')


@admin_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        old = request.form.get('old_password')
        new = request.form.get('new_password')
        admin_username = session.get('admin_username')
        db = get_db()
        admin = db.execute('SELECT * FROM admin WHERE username=?', (admin_username,)).fetchone()
        if admin and check_password_hash(admin['password'], old):
            new_hash = generate_password_hash(new)
            db.execute('UPDATE admin SET password=? WHERE username=?', (new_hash, admin_username))
            db.commit()
            flash('Password updated successfully', 'success')
        else:
            flash('Old password incorrect', 'danger')
    return render_template('admin_change_password.html')


@admin_bp.route('/bookings')
def bookings():
    db = get_db()
    bookings_list = db.execute(
        '''
        SELECT b.*, r.room_no
        FROM bookings b
        LEFT JOIN rooms r ON b.room_id = r.id
        ORDER BY b.created_at DESC
        '''
    ).fetchall()
    # cleanup old rejected bookings as well
    try:
        db.execute("DELETE FROM payments WHERE booking_id IN (SELECT id FROM bookings WHERE status='Rejected' AND datetime(created_at) <= datetime('now','-5 minutes'))")
        db.execute("DELETE FROM bookings WHERE status='Rejected' AND datetime(created_at) <= datetime('now','-5 minutes')")
        db.commit()
    except Exception:
        pass
    return render_template('admin_bookings.html', bookings=bookings_list)


@admin_bp.route('/notifications')
def notifications():
    db = get_db()
    # Fetch unread notifications for admin
    notes = db.execute("SELECT * FROM notifications WHERE is_read=0 ORDER BY created_at DESC").fetchall()
    # Mark them read so they won't appear again
    try:
        db.execute("UPDATE notifications SET is_read=1 WHERE is_read=0")
        db.commit()
    except Exception:
        pass
    return render_template('admin_notifications.html', notifications=notes)


@admin_bp.route('/visits')
def visits():
    db = get_db()
    # Join visits to students and rooms so admin can see who the visitor is for and which room
    visits_list = db.execute(
        '''
        SELECT v.*, s.name AS student_name, r.room_no AS room_no
        FROM visits v
        LEFT JOIN students s ON v.student_id = s.id
        LEFT JOIN rooms r ON s.room_id = r.id
        ORDER BY v.visit_date DESC, v.visit_time DESC
        '''
    ).fetchall()
    try:
        visits_list = [dict(v) for v in visits_list] if visits_list else []
    except Exception:
        pass
    return render_template('admin_visits.html', visits=visits_list)


@admin_bp.route('/verify_booking', methods=['GET', 'POST'])
def verify_booking():
    db = get_db()
    booking = None
    if request.method == 'POST':
        booking_id = request.form.get('booking_id')
        email = request.form.get('email')
        if not booking_id or not email:
            flash('Provide both Booking ID and Email to verify.', 'danger')
            return redirect('/admin/verify_booking')
        booking = db.execute('SELECT * FROM bookings WHERE booking_id = ? AND LOWER(email) = LOWER(?)', (booking_id, email)).fetchone()
        if not booking:
            flash('No booking found with provided details.', 'danger')
            return redirect('/admin/verify_booking')

        # Check total paid
        total_paid = db.execute('SELECT SUM(amount) as total FROM payments WHERE booking_id=? AND status="Paid"', (booking['id'],)).fetchone()['total'] or 0
        price = booking['price'] or 0
        if price > 0 and total_paid >= (price / 2):
            # Accept booking
            try:
                if booking['room_id']:
                    from hostel_pg_management.models.models import Room
                    Room.update_occupancy(booking['room_id'], increment=True)
                user, temp_password = ensure_booking_user(booking, verified=True)
                try:
                    add_notification('student', user['id'], f'Your booking {booking["booking_id"]} has been confirmed.', 'success')
                except Exception:
                    pass
                db.execute('UPDATE bookings SET status=? WHERE id=?', ('Confirmed', booking['id']))
                db.commit()
                flash('Booking verified and confirmed.', 'success')
                return redirect('/admin/bookings')
            except Exception:
                flash('Failed to confirm booking.', 'danger')
                return redirect('/admin/verify_booking')
        else:
            flash('Insufficient payments. Booking requires at least 50% paid for admin auto-accept.', 'warning')
            return redirect('/admin/verify_booking')

    return render_template('admin_verify_booking.html', booking=booking)
