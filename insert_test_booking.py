import sqlite3
from pathlib import Path

DB = Path('hostel_pg_management') / 'hostel.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Ensure rooms exist: pick room id 1
room = cur.execute('SELECT id FROM rooms ORDER BY id LIMIT 1').fetchone()
room_id = room['id'] if room else None

booking_id = 'BK9999'
exists = cur.execute('SELECT * FROM bookings WHERE booking_id=?', (booking_id,)).fetchone()
if exists:
    print('booking exists')
else:
    cur.execute(
        "INSERT INTO bookings (booking_id, name, phone, email, room_id, sharing_type, ac_type, price, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (booking_id, 'Automated Tester', '9100000000', 'tester@example.com', room_id, 1, 'AC', 9000, 'Pending')
    )
    conn.commit()
    print('booking inserted')

conn.close()
