from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from hostel_pg_management.database.db import get_db
from datetime import datetime

notice_bp = Blueprint('notice', __name__)

# Notices are stored in main DB; use get_db() to access

@notice_bp.before_request
def require_login():
    """Require user to be logged in"""
    if not session.get('admin') and not session.get('student_id'):
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.student_login'))

@notice_bp.route("/board")
def notice_board():
    """Display notice board for all users"""
    try:
        db = get_db()
        notices = db.execute(
            """
            SELECT id, title, message, created_at
            FROM notices
            ORDER BY created_at DESC
            """
        ).fetchall()
        return render_template("notice_board.html", notices=notices)
    except Exception:
        # If notices cannot be loaded, show the notice board page with an empty list
        # and a user-facing flash instead of redirecting to home.
        flash("Error loading notices. Please try again.", "danger")
        return render_template("notice_board.html", notices=[])

@notice_bp.route("/add", methods=["GET", "POST"])
def add_notice():
    """Admin only: Add new notice"""
    if not session.get('admin'):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('notice.notice_board'))

    if request.method == "POST":
        title = request.form.get("title")
        message = request.form.get("message")

        if not title or not message:
            flash("Title and message are required.", "danger")
            return redirect(request.url)

        try:
            db = get_db()
            db.execute(
                "INSERT INTO notices (title, message, admin_id) VALUES (?, ?, ?)",
                (title, message, 1),
            )
            db.commit()
            flash("Notice added successfully.", "success")
            return redirect(url_for('notice.notice_board'))
        except Exception:
            flash("Error adding notice. Please try again.", "danger")
            return redirect(request.url)

    return render_template("add_notice.html")

@notice_bp.route("/delete/<int:notice_id>", methods=["POST"])
def delete_notice(notice_id):
    """Admin only: Delete notice"""
    if not session.get('admin'):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('notice.notice_board'))

    try:
        db = get_db()
        db.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
        db.commit()
        flash("Notice deleted successfully.", "success")
    except Exception:
        flash("Error deleting notice. Please try again.", "danger")

    return redirect(url_for('notice.notice_board'))


@notice_bp.route("/edit/<int:notice_id>", methods=["GET", "POST"])
def edit_notice(notice_id):
    """Admin only: Edit existing notice"""
    if not session.get('admin'):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('notice.notice_board'))

    try:
        db = get_db()
        if request.method == 'POST':
            title = request.form.get('title')
            message = request.form.get('message')
            if not title or not message:
                flash('Title and message required.', 'danger')
                return redirect(request.url)
            db.execute('UPDATE notices SET title=?, message=? WHERE id=?', (title, message, notice_id))
            db.commit()
            flash('Notice updated.', 'success')
            return redirect(url_for('notice.notice_board'))

        notice = db.execute('SELECT * FROM notices WHERE id=?', (notice_id,)).fetchone()
        if not notice:
            flash('Notice not found.', 'danger')
            return redirect(url_for('notice.notice_board'))
        return render_template('edit_notice.html', notice=notice)
    except Exception:
        flash('Error editing notice.', 'danger')
        return redirect(url_for('notice.notice_board'))