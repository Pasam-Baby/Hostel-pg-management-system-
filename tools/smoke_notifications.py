"""Smoke test: verify student notifications are deleted on view."""
import sqlite3
from hostel_pg_management.app import app
from hostel_pg_management.database.db import init_db
from hostel_pg_management.config import Config

# Ensure DB initialized
init_db()

with app.test_client() as client:
    # Create a test student if not exists
    db_path = Config.DATABASE
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Insert student
    cur.execute("SELECT id FROM students WHERE LOWER(email)=LOWER(?)", ('test_student@example.com',))
    row = cur.fetchone()
    if row:
        sid = row[0]
    else:
        cur.execute("INSERT INTO students (name, email, phone, password) VALUES (?, ?, ?, ?)", ('Test Student', 'test_student@example.com', '9999999999', 'pass'))
        sid = cur.lastrowid
    # Insert a student-specific notification (match current schema: message, notification_type)
    cur.execute("INSERT INTO notifications (user_type, user_id, message, notification_type, is_read, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))", ('student', sid, 'This is a test', 'info', 0))
    conn.commit()
    conn.close()

    # Set session to simulate logged-in student
    with client.session_transaction() as sess:
        sess['student_id'] = sid
        sess['student_name'] = 'Test Student'

    # Fetch notifications page
    resp = client.get('/student/notifications')
    print('GET /student/notifications status_code=', resp.status_code)
    # Now check DB to ensure notification was removed
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM notifications WHERE user_type='student' AND user_id=?", (sid,))
    cnt = cur.fetchone()['c']
    print('Remaining student notifications count after view:', cnt)
    if cnt == 0:
        print('SUCCESS: student notifications deleted on view')
    else:
        print('FAIL: notifications still present')
    conn.close()
