import sqlite3
import os

DATABASE = r'c:\Users\hp\OneDrive\Desktop\hostel_pg_management (5)\hostel_pg_management\hostel.db'

def ensure_column(cur, table_name, column_name, definition):
    try:
        columns = [column[1] for column in cur.execute(f"PRAGMA table_info({table_name})").fetchall()]
        if column_name not in columns:
            print(f"Adding column {column_name} to table {table_name}")
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        else:
            print(f"Column {column_name} already exists in table {table_name}")
    except Exception as e:
        print(f"Error ensuring column {column_name} in {table_name}: {e}")

def fix():
    if not os.path.exists(DATABASE):
        print(f"Database not found at {DATABASE}")
        return

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    # Ensure tables exists (should be created by init_db but let's be double sure)
    cur.execute("CREATE TABLE IF NOT EXISTS facilities (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS food_menu (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, breakfast TEXT, lunch TEXT, dinner TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, admin_id INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS complaints (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, subject TEXT NOT NULL, complaint TEXT NOT NULL, status TEXT DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (student_id) REFERENCES students(id))")
    cur.execute("CREATE TABLE IF NOT EXISTS complaint_replies (id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER NOT NULL, admin_id INTEGER, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (complaint_id) REFERENCES complaints(id), FOREIGN KEY (admin_id) REFERENCES admin(id))")
    cur.execute("CREATE TABLE IF NOT EXISTS id_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, id_proof_path TEXT, verification_status TEXT DEFAULT 'Pending', verified_by INTEGER, verified_at TIMESTAMP, remarks TEXT, FOREIGN KEY (student_id) REFERENCES students(id), FOREIGN KEY (verified_by) REFERENCES admin(id))")
    cur.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_type TEXT NOT NULL, user_id INTEGER, message TEXT NOT NULL, notification_type TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, visit_date TEXT NOT NULL, visit_time TEXT NOT NULL, status TEXT DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

    # Ensure missing columns in payments
    ensure_column(cur, "payments", "payment_month", "TEXT")
    ensure_column(cur, "payments", "payment_date", "TEXT")
    ensure_column(cur, "payments", "due_date", "TEXT")
    ensure_column(cur, "payments", "status", "TEXT DEFAULT 'Pending'")
    ensure_column(cur, "payments", "late_fee", "INTEGER DEFAULT 0")
    ensure_column(cur, "payments", "receipt_path", "TEXT")
    ensure_column(cur, "payments", "booking_id", "INTEGER")

    # Ensure missing columns in visits
    ensure_column(cur, "visits", "relation", "TEXT")
    ensure_column(cur, "visits", "student_id", "INTEGER")

    # Ensure missing columns in students
    ensure_column(cur, "students", "room_id", "INTEGER")
    ensure_column(cur, "students", "id_proof", "TEXT")
    ensure_column(cur, "students", "is_verified", "INTEGER DEFAULT 0")
    ensure_column(cur, "students", "approved", "INTEGER DEFAULT 0")

    # Ensure missing columns in rooms
    ensure_column(cur, "rooms", "category", "TEXT DEFAULT 'Comfort'")
    ensure_column(cur, "rooms", "sharing_type", "INTEGER NOT NULL DEFAULT 2")
    ensure_column(cur, "rooms", "ac_type", "TEXT NOT NULL DEFAULT 'Non-AC'")
    ensure_column(cur, "rooms", "total_beds", "INTEGER NOT NULL DEFAULT 2")
    ensure_column(cur, "rooms", "available_beds", "INTEGER NOT NULL DEFAULT 2")
    ensure_column(cur, "rooms", "price", "INTEGER NOT NULL DEFAULT 4000")
    ensure_column(cur, "rooms", "status", "TEXT DEFAULT 'available'")
    ensure_column(cur, "rooms", "occupied", "INTEGER DEFAULT 0")

    # Ensure missing columns in bookings
    ensure_column(cur, "bookings", "sharing_type", "INTEGER")
    ensure_column(cur, "bookings", "ac_type", "TEXT")
    ensure_column(cur, "bookings", "price", "INTEGER")
    ensure_column(cur, "bookings", "status", "TEXT DEFAULT 'Pending'")
    ensure_column(cur, "bookings", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column(cur, "bookings", "address", "TEXT")
    ensure_column(cur, "bookings", "password_hash", "TEXT")

    conn.commit()
    conn.close()
    print("Database fix complete.")

if __name__ == "__main__":
    fix()
