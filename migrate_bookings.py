import sqlite3, os
from hostel_pg_management.config import Config

db_path = Config.DATABASE
print('DB path:', db_path)
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cols = [c[1] for c in cur.execute("PRAGMA table_info(bookings)").fetchall()]
print('Existing columns:', cols)
expected = {
    'booking_id': "TEXT UNIQUE",
    'name': "TEXT",
    'phone': "TEXT",
    'email': "TEXT",
    'room_id': "INTEGER",
    'sharing_type': "INTEGER",
    'ac_type': "TEXT",
    'price': "INTEGER DEFAULT 0",
    'status': "TEXT DEFAULT 'Pending'",
    'created_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}
for col, definition in expected.items():
    if col not in cols:
        sql = f"ALTER TABLE bookings ADD COLUMN {col} {definition}"
        print('Adding column:', col)
        cur.execute(sql)
    else:
        print('Already has:', col)
conn.commit()
conn.close()
print('Migration complete')
