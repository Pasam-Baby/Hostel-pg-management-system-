"""Smoke test: verify student dashboard top cards render and link correctly."""
import sqlite3
from hostel_pg_management.app import app
from hostel_pg_management.database.db import init_db
from hostel_pg_management.config import Config

init_db()

db_path = Config.DATABASE
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Ensure a test student exists
cur.execute("SELECT id FROM students WHERE LOWER(email)=LOWER(?)", ('smoke_student@example.com',))
row = cur.fetchone()
if row:
    sid = row[0]
else:
    cur.execute("INSERT INTO students (name, email, phone, password) VALUES (?, ?, ?, ?)", ('Smoke Student', 'smoke_student@example.com', '9999999998', 'pass'))
    sid = cur.lastrowid
conn.commit()
conn.close()

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['student_id'] = sid
        sess['student_name'] = 'Smoke Student'

    resp = client.get('/student/dashboard')
    print('GET /student/dashboard status_code=', resp.status_code)
    html = resp.get_data(as_text=True)

    checks = {
        'payments_link': '/student/payments' in html,
        'complaints_link': '/student/complaints' in html,
        'visits_link': '/student/visits' in html,
    }

    for k, v in checks.items():
        print(f"{k}:", 'FOUND' if v else 'MISSING')

    if resp.status_code == 200 and all(checks.values()):
        print('SUCCESS: dashboard top cards present and linked')
    else:
        print('FAIL: dashboard check failed')
