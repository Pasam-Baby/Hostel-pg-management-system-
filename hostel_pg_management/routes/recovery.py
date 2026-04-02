from flask import Blueprint, render_template, request, flash, redirect, url_for
from hostel_pg_management.database.db import get_db
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer
from hostel_pg_management.config import Config
from hostel_pg_management.utils.mail import send_email

recovery_bp = Blueprint('recovery', __name__)

def get_serializer():
    return URLSafeTimedSerializer(Config.SECRET_KEY)

@recovery_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        db = get_db()
        
        # Check student
        student = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
        admin = db.execute("SELECT * FROM admin WHERE email=?", (email,)).fetchone()
        
        if student or admin:
            s = get_serializer()
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for("recovery.reset_password", token=token, _external=True)
            
            html = f"<h3>Password Reset</h3><p>Click <a href='{reset_url}'>here</a> to reset your password. This link expires in 1 hour.</p>"
            send_email(email, "Password Reset", html)
            flash("An email with password reset instructions has been sent.", "info")
            return redirect("/")
        else:
            flash("If that email exists in our system, a reset link was sent.", "info")
            return redirect("/")
            
    return render_template("forgot_password.html")

@recovery_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect("/")

    if request.method == "POST":
        password = request.form.get("password")
        hashed_pw = generate_password_hash(password)
        db = get_db()
        
        student = db.execute("SELECT * FROM students WHERE email=?", (email,)).fetchone()
        if student:
            db.execute("UPDATE students SET password=? WHERE email=?", (hashed_pw, email))
            
        admin = db.execute("SELECT * FROM admin WHERE email=?", (email,)).fetchone()
        if admin:
            db.execute("UPDATE admin SET password=? WHERE email=?", (hashed_pw, email))
            
        db.commit()
        flash("Your password has been updated. You can now log in.", "success")
        return redirect("/")
            
    return render_template("reset_password.html")
