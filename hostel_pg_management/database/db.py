import sqlite3

from flask import g

from hostel_pg_management.config import Config


def ensure_column(cur, table_name, column_name, definition):
    columns = [column[1] for column in cur.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(Config.DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE
        )
        """
    )
    admin_exists = cur.execute("SELECT * FROM admin WHERE username='admin'").fetchone()
    if not admin_exists:
        from werkzeug.security import generate_password_hash
        # Default admin credentials: Username: admin, Password: admin123
        admin_hash = generate_password_hash("admin123")
        cur.execute("INSERT INTO admin (username, password) VALUES ('admin', ?)", (admin_hash,))
    
    # Ensure tables exists (for cases where they might have been missing)
    cur.execute("CREATE TABLE IF NOT EXISTS facilities (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS food_menu (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, breakfast TEXT, lunch TEXT, dinner TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, admin_id INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS complaint_replies (id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER NOT NULL, admin_id INTEGER, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (complaint_id) REFERENCES complaints(id), FOREIGN KEY (admin_id) REFERENCES admin(id))")
    cur.execute("CREATE TABLE IF NOT EXISTS id_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, id_proof_path TEXT, verification_status TEXT DEFAULT 'Pending', verified_by INTEGER, verified_at TIMESTAMP, remarks TEXT, FOREIGN KEY (student_id) REFERENCES students(id), FOREIGN KEY (verified_by) REFERENCES admin(id))")
    cur.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_type TEXT NOT NULL, user_id INTEGER, message TEXT NOT NULL, notification_type TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_no TEXT NOT NULL UNIQUE,
            sharing_type INTEGER NOT NULL DEFAULT 2,
            ac_type TEXT NOT NULL DEFAULT 'Non-AC',
            total_beds INTEGER NOT NULL DEFAULT 2,
            available_beds INTEGER NOT NULL DEFAULT 2,
            price INTEGER NOT NULL DEFAULT 4000,
            status TEXT DEFAULT 'available',
            occupied INTEGER DEFAULT 0
        )
        """
    )
    ensure_column(cur, "rooms", "sharing_type", "INTEGER NOT NULL DEFAULT 2")
    ensure_column(cur, "rooms", "ac_type", "TEXT NOT NULL DEFAULT 'Non-AC'")
    ensure_column(cur, "rooms", "total_beds", "INTEGER NOT NULL DEFAULT 2")
    ensure_column(cur, "rooms", "available_beds", "INTEGER NOT NULL DEFAULT 2")
    ensure_column(cur, "rooms", "price", "INTEGER NOT NULL DEFAULT 4000")
    ensure_column(cur, "rooms", "status", "TEXT DEFAULT 'available'")
    ensure_column(cur, "rooms", "occupied", "INTEGER DEFAULT 0")
    ensure_column(cur, "rooms", "category", "TEXT DEFAULT 'Comfort'")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            room_id INTEGER,
            sharing_type INTEGER,
            ac_type TEXT,
            price INTEGER,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )
    ensure_column(cur, "bookings", "sharing_type", "INTEGER")
    ensure_column(cur, "bookings", "ac_type", "TEXT")
    ensure_column(cur, "bookings", "price", "INTEGER")
    ensure_column(cur, "bookings", "status", "TEXT DEFAULT 'Pending'")
    ensure_column(cur, "bookings", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column(cur, "bookings", "address", "TEXT")
    ensure_column(cur, "bookings", "password_hash", "TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            visit_time TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_column(cur, "visits", "relation", "TEXT")
    ensure_column(cur, "visits", "student_id", "INTEGER")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS id_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            id_proof_path TEXT,
            verification_status TEXT DEFAULT 'Pending',
            verified_by INTEGER,
            verified_at TIMESTAMP,
            remarks TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (verified_by) REFERENCES admin(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Notices: admin-managed announcements (previously kept in a separate notice.db)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id INTEGER
        )
        """
    )

    # NOTE: previous versions seeded sample rooms here. Seeding removed to ensure
    # the application's single source of truth is the `rooms` table managed at runtime
    # (bookings/admin). Existing databases that already contain sample rooms will
    # retain them; if you want to remove those rows, run a cleanup SQL script.

    cur.execute(
        """
        UPDATE rooms
        SET total_beds = CASE
                WHEN sharing_type BETWEEN 1 AND 4 THEN sharing_type
                ELSE total_beds
            END,
            price = CASE
                WHEN sharing_type = 1 AND ac_type = 'AC' THEN 9000
                WHEN sharing_type = 1 AND ac_type = 'Non-AC' THEN 6000
                WHEN sharing_type = 2 AND ac_type = 'AC' THEN 7500
                WHEN sharing_type = 2 AND ac_type = 'Non-AC' THEN 6000
                WHEN sharing_type = 3 AND ac_type = 'AC' THEN 6500
                WHEN sharing_type = 3 AND ac_type = 'Non-AC' THEN 5500
                WHEN sharing_type = 4 AND ac_type = 'AC' THEN 6000
                WHEN sharing_type = 4 AND ac_type = 'Non-AC' THEN 5000
                ELSE price
            END
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            room_id INTEGER,
            id_proof TEXT,
            is_verified INTEGER DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )
    ensure_column(cur, "students", "room_id", "INTEGER")
    ensure_column(cur, "students", "id_proof", "TEXT")
    ensure_column(cur, "students", "is_verified", "INTEGER DEFAULT 0")

    from werkzeug.security import generate_password_hash

    # NOTE: sample student seeding removed. Create real users through normal booking
    # flows or via admin tools. Existing sample users (if any) are left untouched.

    cur.execute("UPDATE rooms SET occupied = (SELECT COUNT(*) FROM students WHERE students.room_id = rooms.id)")
    cur.execute("UPDATE rooms SET available_beds = MAX(0, total_beds - occupied)")
    cur.execute("UPDATE rooms SET status = CASE WHEN available_beds <= 0 THEN 'occupied' ELSE 'available' END")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            booking_id INTEGER,
            amount INTEGER NOT NULL,
            payment_month TEXT NOT NULL,
            payment_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            late_fee INTEGER DEFAULT 0,
            receipt_path TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        )
        """
    )
    ensure_column(cur, "payments", "payment_month", "TEXT NOT NULL")
    ensure_column(cur, "payments", "payment_date", "TEXT NOT NULL")
    ensure_column(cur, "payments", "due_date", "TEXT NOT NULL")
    ensure_column(cur, "payments", "status", "TEXT DEFAULT 'Pending'")
    ensure_column(cur, "payments", "booking_id", "INTEGER")
    ensure_column(cur, "payments", "late_fee", "INTEGER DEFAULT 0")
    ensure_column(cur, "payments", "receipt_path", "TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            complaint TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
        """
    )

    # Replies to complaints so admin can respond and history is stored
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS complaint_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            admin_id INTEGER,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(id),
            FOREIGN KEY (admin_id) REFERENCES admin(id)
        )
        """
    )

    complaint_count = cur.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    if complaint_count == 0:
        alice_id = cur.execute("SELECT id FROM students WHERE email='alice@gmail.com'").fetchone()
        ramya_id = cur.execute("SELECT id FROM students WHERE email='ramya@gmail.com'").fetchone()
        riya_id = cur.execute("SELECT id FROM students WHERE email='riya@gmail.com'").fetchone()
        if alice_id and ramya_id and riya_id:
            sample_complaints = [
                (alice_id[0], "WiFi Issue", "The WiFi in my room disconnects often.", "Pending"),
                (ramya_id[0], "Room Cleaning", "Cleaning support is needed in the corridor area.", "In Progress"),
                (riya_id[0], "Water Heater", "The water heater needs servicing.", "Resolved"),
            ]
            cur.executemany(
                "INSERT INTO complaints (student_id, subject, complaint, status) VALUES (?, ?, ?, ?)",
                sample_complaints,
            )

    conn.commit()
    conn.close()

    # Settings table to store configurable values like emergency contact
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        '''
    )
    # Seed default emergency contact if missing
    existing = cur.execute("SELECT value FROM settings WHERE key='emergency_number'").fetchone()
    if not existing:
        cur.execute("INSERT INTO settings (key, value) VALUES ('emergency_number', '+91 98765 40000')")

    # Seed two sample notices if none exist
    notice_count = cur.execute('SELECT COUNT(*) FROM notices').fetchone()[0]
    if notice_count == 0:
        sample_notices = [
            ('Maintenance Window', 'Water supply interruption expected on Sunday 10 AM - 2 PM.'),
            ('Guest Lecture', 'A guest lecture on career guidance is scheduled for Friday at 4 PM in the common hall.'),
        ]
        cur.executemany('INSERT INTO notices (title, message, admin_id) VALUES (?, ?, ?)', [(t,m,1) for (t,m) in sample_notices])

    conn.commit()
    conn.close()
    print("Database initialized successfully!")

    # Also ensure food_menu and facilities tables exist in main DB for admin-managed content
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS food_menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            breakfast TEXT,
            lunch TEXT,
            dinner TEXT
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
        '''
    )
    # Seed weekly menu if empty
    count = cur.execute("SELECT COUNT(*) FROM food_menu").fetchone()[0]
    if count == 0:
        sample = [
            ('Sunday', 'Masala Dosa', 'Rice, Paneer Curry, Salad', 'Chapati, Dal Fry'),
            ('Monday', 'Idli & Sambar', 'Rice, Dal, Veg Curry', 'Chapati, Paneer Masala'),
            ('Tuesday', 'Dosa & Chutney', 'Rice, Rajma, Salad', 'Jeera Rice, Mix Veg'),
            ('Wednesday', 'Poha & Fruit', 'Rice, Chole, Curd', 'Chapati, Aloo Mutter'),
            ('Thursday', 'Upma & Chutney', 'Lemon Rice, Sambar', 'Paratha, Veg Kurma'),
            ('Friday', 'Aloo Paratha', 'Rice, Sambar, Fry', 'Chapati, Dal Tadka'),
            ('Saturday', 'Puri Bhaji', 'Veg Biryani, Raita', 'Noodles, Gobi Manchurian'),
        ]
        cur.executemany('INSERT INTO food_menu (day, breakfast, lunch, dinner) VALUES (?, ?, ?, ?)', sample)

    # Seed facilities if missing specific entries
    required_facs = [
        ('WiFi', 'High-speed internet across campus'),
        ('Laundry', 'On-site laundry services available'),
        ('CCTV', 'CCTV monitoring across common areas'),
        ('Security', '24/7 security personnel and CCTV monitoring'),
        ('Power Backup', 'Uninterrupted power supply with backup generators')
    ]
    existing = cur.execute('SELECT name FROM facilities').fetchall()
    existing_names = {r[0] for r in existing}
    to_insert = [f for f in required_facs if f[0] not in existing_names]
    if to_insert:
        cur.executemany('INSERT INTO facilities (name, description) VALUES (?, ?)', to_insert)
    # Ensure rooms 1..300 exist (idempotent). This centralizes room data in DB.
    existing_rooms = cur.execute('SELECT COUNT(*) FROM rooms').fetchone()[0]
    if existing_rooms < 300:
        created = 0
        for i in range(1, 301):
            rn = str(i)
            exists = cur.execute('SELECT id FROM rooms WHERE room_no = ?', (rn,)).fetchone()
            if exists:
                continue
            # Distribute sharing types 1..4 in round-robin and alternate AC/Non-AC
            sharing = ((i - 1) % 4) + 1
            ac = 'AC' if (i % 2 == 0) else 'Non-AC'
            # Price mapping per spec
            if sharing == 1 and ac == 'AC':
                price = 9000
            elif sharing == 1 and ac == 'Non-AC':
                price = 6000
            elif sharing == 2 and ac == 'AC':
                price = 7500
            elif sharing == 2 and ac == 'Non-AC':
                price = 6000
            elif sharing == 3 and ac == 'AC':
                price = 6500
            elif sharing == 3 and ac == 'Non-AC':
                price = 5500
            elif sharing == 4 and ac == 'AC':
                price = 6000
            else:
                price = 5000
            cur.execute('INSERT INTO rooms (room_no, sharing_type, ac_type, total_beds, available_beds, price, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (rn, sharing, ac, sharing, sharing, price, 'available'))
            created += 1
        if created:
            conn.commit()
    conn.close()
