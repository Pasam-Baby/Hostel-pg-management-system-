import os
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from hostel_pg_management.database.db import get_db
from hostel_pg_management.models.models import Room
from hostel_pg_management.utils.oauth import oauth
from hostel_pg_management.routes.booking import add_notification

auth_bp = Blueprint('auth', __name__)

# ---------------- ADMIN LOGIN ----------------
@auth_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username")
        password = request.form.get("password")

        admin = db.execute("SELECT * FROM admin WHERE LOWER(username)=LOWER(?)", (username,)).fetchone()
        
        if admin:
            try:
                admin_pwd = admin["password"]
            except KeyError:
                admin_pwd = admin[2] # Fallback for tuple vs object
                
            is_valid = False
            if admin_pwd == password:
                is_valid = True
            else:
                try:
                    if check_password_hash(admin_pwd, password):
                        is_valid = True
                except ValueError:
                    pass

            if is_valid:
                session["admin"] = True
                session["admin_username"] = admin["username"]
                flash("Login successful", "success")
                return redirect("/admin/dashboard")

        flash("Wrong Credentials", "danger")
        return redirect("/admin_login")

    return render_template("login.html")

# ---------------- STUDENT LOGIN ----------------
@auth_bp.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        db = get_db()
        email = request.form.get("email")
        password = request.form.get("password")

        # Required query by prompt (using email, we check hash in python)
        student = db.execute("SELECT * FROM students WHERE LOWER(email)=LOWER(?)", (email,)).fetchone()

        if student:
            try:
                student_pwd = student["password"]
            except KeyError:
                student_pwd = student[3] # Fallback for tuple vs object
                
            is_valid = False
            if student_pwd == password:
                is_valid = True
            else:
                try:
                    if check_password_hash(student_pwd, password):
                        is_valid = True
                except ValueError:
                    pass

            if is_valid:
                # Ensure account has been approved by admin
                try:
                    is_verified = int(student.get('is_verified', 0)) if hasattr(student, 'get') else int(student['is_verified'])
                except Exception:
                    is_verified = 0

                if not is_verified:
                    flash("Account not yet approved by admin. Please wait for confirmation.", "warning")
                    return redirect("/student_login")

                session["student_id"] = student["id"]
                session["student_name"] = student["name"]
                flash("Login successful", "success")
                return redirect("/student/dashboard")

        flash("Invalid credentials", "danger")
        return redirect("/student_login")

    return render_template("student_login.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login_alias():
    return student_login()

# ---------------- STUDENT REGISTRATION ----------------
@auth_bp.route('/student_register', methods=["GET", "POST"])
def student_register():
    db = get_db()
    available_rooms = Room.get_available()

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        room_id = request.form.get("room_id") or None

        # Auto-assign room if user did not pick a specific one
        if not room_id and available_rooms:
            room_id = available_rooms[0]["id"]

        existing = db.execute("SELECT * FROM students WHERE LOWER(email)=LOWER(?)", (email,)).fetchone()
        if existing:
            flash("A user with this email already exists. Please log in.", "warning")
            return redirect(url_for('auth.student_login'))

        if room_id:
            room_check = db.execute("SELECT available_beds FROM rooms WHERE id=?", (room_id,)).fetchone()
            if room_check and room_check["available_beds"] <= 0:
                flash("Selected room is already full. Please choose another room.", "danger")
                return redirect(url_for('auth.student_register'))

        id_proof = request.files.get("id_proof")
        id_proof_path = None
        if id_proof and id_proof.filename:
            filename = secure_filename(id_proof.filename)
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            saved_path = os.path.join(upload_folder, filename)
            id_proof.save(saved_path)
            id_proof_path = f"uploads/{filename}"

        hashed_password = generate_password_hash(password)
        db.execute(
            "INSERT INTO students (name, email, password, phone, room_id, id_proof, is_verified) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, email, hashed_password, phone, room_id, id_proof_path, 0)
        )

        if room_id:
            Room.update_occupancy(room_id, increment=True)

        db.commit()

        session["student_id"] = db.execute("SELECT id FROM students WHERE LOWER(email)=LOWER(?)", (email,)).fetchone()["id"]
        session["student_name"] = name
        flash("Registration successful. Welcome!", "success")
        return redirect(url_for('student.dashboard'))

    return render_template("student_register.html", rooms=available_rooms)

# ---------------- GOOGLE OAUTH ----------------
@auth_bp.route('/google_login')
def google_login():
    # Detect the role attempting to login
    role = request.args.get('role', 'student')
    session['google_login_role'] = role
    
    redirect_uri = url_for('auth.google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/google_auth')
def google_auth():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        flash("Google Auth Failed.", "danger")
        return redirect("/")

    email = user_info.get("email")
    db = get_db()
    
    try:
        role = session.pop('google_login_role', 'student')
    except Exception:
        role = 'student'
        
    if role == 'admin':
        admin = db.execute("SELECT * FROM admin WHERE LOWER(username)=LOWER(?)", (email,)).fetchone()
        if admin:
            session["admin"] = True
            session["admin_username"] = admin["username"]
            flash("Admin Google Login successful", "success")
            return redirect("/admin/dashboard")
        flash(f"No admin account found for {email}", "danger")
        return redirect("/admin_login")
    else:
        student = db.execute("SELECT * FROM students WHERE LOWER(email)=LOWER(?)", (email,)).fetchone()
        if student:
            try:
                is_verified = int(student.get('is_verified', 0)) if hasattr(student, 'get') else int(student['is_verified'])
            except Exception:
                is_verified = 0

            if not is_verified:
                flash(f"Account for {email} is not yet approved by administration.", "warning")
                return redirect("/student_login")

            session["student_id"] = student["id"]
            session["student_name"] = student["name"]
            flash("Google Login successful", "success")
            return redirect("/student/dashboard")
        flash(f"No student record found for {email}. Please contact administration.", "danger")
        return redirect("/student_login")

# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")

# ---------------- SCHEDULE VISIT ----------------
@auth_bp.route("/schedule_visit", methods=["GET", "POST"])
def schedule_visit():
    db = get_db()
    if request.method == "POST":
        db = get_db()
        name = request.form.get("name")
        relation = request.form.get("relation")
        email = request.form.get("email")
        phone = request.form.get("phone")
        visit_date = request.form.get("visit_date")
        visit_time = request.form.get("visit_time")
        # Relation validation: accept common relations but be tolerant to freeform input
        try:
            allowed_relations = {"Father", "Mother", "Brother", "Sister"}
            if not relation:
                relation = 'N/A'
            # keep provided relation even if it's not in allowed set (avoid blocking submissions)
        except Exception:
            relation = relation or 'N/A'
        # Validate input
        if not all([name, email, phone, visit_date, visit_time]):
            flash('All fields are required', 'danger')
            return redirect(url_for('auth.schedule_visit'))
        
        # Validate email format
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address', 'danger')
            return redirect(url_for('auth.schedule_visit'))
        
        # Validate date is not in the past. Accept multiple time formats.
        dt_string = f"{visit_date} {visit_time}".strip()
        parse_success = False
        for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
            try:
                visit_datetime = datetime.strptime(dt_string, fmt)
                parse_success = True
                break
            except ValueError:
                continue
        if not parse_success:
            # Try a more forgiving isoformat parse as a last resort
            try:
                # fromisoformat accepts 'YYYY-MM-DDTHH:MM:SS' and variants
                visit_datetime = datetime.fromisoformat(dt_string)
                parse_success = True
            except Exception:
                pass

        if not parse_success:
            # Log invalid date/time input for diagnostics
            try:
                import traceback
                with open('server_errors.log', 'a', encoding='utf-8') as fh:
                    fh.write('\n--- schedule_visit parse error ---\n')
                    fh.write('form: ' + str({k: request.form.get(k) for k in ['name','relation','email','phone','visit_date','visit_time']}) + '\n')
                    fh.write('parse input: ' + dt_string + '\n')
                    fh.write('Expected formats: %Y-%m-%d %H:%M or %Y-%m-%d %H:%M:%S or ISO\n')
                    fh.write('\n')
            except Exception:
                pass
            flash('Invalid date or time format', 'danger')
            return redirect(url_for('auth.schedule_visit'))

        if visit_datetime < datetime.now():
            flash('Visit date cannot be in the past', 'danger')
            return redirect(url_for('auth.schedule_visit'))

        # Normalize stored date/time (strip seconds) so comparisons are consistent
        visit_date = visit_datetime.strftime('%Y-%m-%d')
        visit_time = visit_datetime.strftime('%H:%M')

        # Check if visit already exists for this date/time
        existing = db.execute(
            "SELECT * FROM visits WHERE visit_date = ? AND visit_time = ?",
            (visit_date, visit_time)
        ).fetchone()
        
        if existing:
            flash('This time slot is already booked. Please choose another time.', 'warning')
            return redirect(url_for('auth.schedule_visit'))
        # Ensure visits table has student_id, room_id, person_to_visit and for_room_no columns
        try:
            cur = db.cursor()
            cur.execute("PRAGMA table_info(visits)")
            cols = [r[1] for r in cur.fetchall()]
            if 'student_id' not in cols:
                try:
                    cur.execute("ALTER TABLE visits ADD COLUMN student_id INTEGER")
                    db.commit()
                except Exception:
                    pass
            if 'room_id' not in cols:
                try:
                    cur.execute("ALTER TABLE visits ADD COLUMN room_id INTEGER")
                    db.commit()
                except Exception:
                    pass
            if 'person_to_visit' not in cols:
                try:
                    cur.execute("ALTER TABLE visits ADD COLUMN person_to_visit TEXT")
                    db.commit()
                except Exception:
                    pass
            if 'for_room_no' not in cols:
                try:
                    cur.execute("ALTER TABLE visits ADD COLUMN for_room_no TEXT")
                    db.commit()
                except Exception:
                    pass
        except Exception:
            pass

        # Capture optional form fields: person_to_visit (name) and for_room_id (room number)
        person_to_visit = request.form.get('person_to_visit') or None
        for_room_no = request.form.get('for_room_id') or None

        # Try to resolve provided person_to_visit / for_room_no to student_id/room_id when possible
        resolved_student_id = None
        resolved_room_id = None
        try:
            # If a room number is provided, attempt to find its id
            if for_room_no:
                r = db.execute('SELECT id FROM rooms WHERE room_no = ?', (for_room_no,)).fetchone()
                if r:
                    resolved_room_id = r['id']
            # If a person_to_visit provided, try to find matching student by name or by room
            if person_to_visit:
                s = db.execute('SELECT id, room_id FROM students WHERE LOWER(name)=LOWER(?) LIMIT 1', (person_to_visit,)).fetchone()
                if s:
                    resolved_student_id = s['id']
                    # prefer student's room if available
                    if s.get('room_id'):
                        resolved_room_id = s['room_id']
                else:
                    # fallback: if for_room_no matched a room, find student in that room
                    if resolved_room_id:
                        s2 = db.execute('SELECT id FROM students WHERE room_id=? LIMIT 1', (resolved_room_id,)).fetchone()
                        if s2:
                            resolved_student_id = s2['id']
        except Exception:
            pass

        # Insert visit, include student_id and room_id when available and when columns exist
        try:
            cur = db.cursor()
            cur.execute("PRAGMA table_info(visits)")
            cols = [r[1] for r in cur.fetchall()]

            fields = ['name', 'relation', 'email', 'phone', 'visit_date', 'visit_time']
            params = [name, relation, email, phone, visit_date, visit_time]

            # include optional textual person/room columns
            if 'person_to_visit' in cols and person_to_visit:
                fields.append('person_to_visit')
                params.append(person_to_visit)
            if 'for_room_no' in cols and for_room_no:
                fields.append('for_room_no')
                params.append(for_room_no)

            student_row = None
            if 'student_id' in cols:
                # prefer explicit resolution, else use logged-in student
                if resolved_student_id:
                    fields.append('student_id')
                    params.append(resolved_student_id)
                elif session.get('student_id'):
                    student_row = db.execute('SELECT id, room_id, name FROM students WHERE id=?', (session.get('student_id'),)).fetchone()
                    fields.append('student_id')
                    params.append(session.get('student_id'))

            if 'room_id' in cols:
                # prefer explicitly resolved room, else linked student room
                if resolved_room_id:
                    fields.append('room_id')
                    params.append(resolved_room_id)
                else:
                    room_id_val = None
                    if 'student_row' in locals() and student_row and 'room_id' in student_row.keys():
                        room_id_val = student_row['room_id']
                    if room_id_val:
                        fields.append('room_id')
                        params.append(room_id_val)

            placeholders = ','.join(['?'] * len(fields))
            sql = f"INSERT INTO visits ({','.join(fields)}) VALUES ({placeholders})"
            db.execute(sql, tuple(params))
        except Exception as ex:
            # log detailed error and fallback simple insert
            try:
                import traceback
                with open('server_errors.log', 'a', encoding='utf-8') as fh:
                    fh.write('\n--- schedule_visit insert error ---\n')
                    fh.write('form: ' + str({k: request.form.get(k) for k in ['name','relation','email','phone','visit_date','visit_time']}) + '\n')
                    fh.write(traceback.format_exc())
                    fh.write('\n')
            except Exception:
                pass
            db.execute(
                "INSERT INTO visits (name, relation, email, phone, visit_date, visit_time) VALUES (?, ?, ?, ?, ?, ?)",
                (name, relation, email, phone, visit_date, visit_time)
            )
        # Notify admin of new visit request
        try:
            add_notification('admin', None, f'New visit request from {name} ({relation}) on {visit_date} at {visit_time}', 'info')
        except Exception:
            pass
        db.commit()

        flash(f"Visit scheduled successfully for {visit_date} at {visit_time}.", "success")
        return redirect(url_for('auth.schedule_visit'))

    today = datetime.now().strftime('%Y-%m-%d')
    # Prefill form fields for logged-in students
    pre_name = ''
    pre_email = ''
    pre_phone = ''
    pre_room_no = None
    try:
        if session.get('student_id'):
            student = db.execute('SELECT name, email, phone, room_id FROM students WHERE id=?', (session.get('student_id'),)).fetchone()
            if student:
                pre_name = student['name'] or ''
                pre_email = student['email'] or ''
                pre_phone = student['phone'] or ''
                if student.get('room_id'):
                    rn = db.execute('SELECT room_no FROM rooms WHERE id=?', (student['room_id'],)).fetchone()
                    pre_room_no = rn['room_no'] if rn else None
    except Exception:
        pass

    return render_template("schedule_visit.html", today_date=today, pre_name=pre_name, pre_email=pre_email, pre_phone=pre_phone, pre_room_no=pre_room_no)


@auth_bp.route("/visit", methods=["GET", "POST"])
def visit_alias():
    return schedule_visit()
