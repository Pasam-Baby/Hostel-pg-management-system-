import sqlite3
from hostel_pg_management.config import Config

DB = Config.DATABASE
print('DB:', DB)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cols = [c[1] for c in cur.execute("PRAGMA table_info(bookings)").fetchall()]
print('Existing bookings columns:', cols)

# If student_id exists and is NOT NULL (we detect by name present), migrate to new schema
# We'll create bookings_new with desired columns and copy data.
cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'")
row = cur.fetchone()
print('Existing bookings SQL:\n', row[0] if row else '')

print('Creating new bookings table...')
cur.execute('''
CREATE TABLE IF NOT EXISTS bookings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT UNIQUE NOT NULL,
    name TEXT,
    phone TEXT,
    email TEXT,
    room_id INTEGER,
    sharing_type INTEGER,
    ac_type TEXT,
    price INTEGER,
    status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(id)
)
''')

# Copy data from old table to new, mapping columns when available
old_cols = cols
select_cols = []
for col in ['booking_id','name','phone','email','room_id','sharing_type','ac_type','price','status','created_at']:
    if col in old_cols:
        select_cols.append(col)
    else:
        select_cols.append(f"NULL AS {col}")

select_sql = "SELECT " + ", ".join(select_cols) + " FROM bookings"
print('Copying data with:', select_sql)
try:
    cur.execute(select_sql)
    rows = cur.fetchall()
    print('Rows to copy:', len(rows))
    for r in rows:
        cur.execute(
            "INSERT OR IGNORE INTO bookings_new (booking_id,name,phone,email,room_id,sharing_type,ac_type,price,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [r['booking_id'], r.get('name'), r.get('phone'), r.get('email'), r.get('room_id'), r.get('sharing_type'), r.get('ac_type'), r.get('price'), r.get('status'), r.get('created_at')]
        )
    conn.commit()
    # Backup old table
    cur.execute("ALTER TABLE bookings RENAME TO bookings_old")
    cur.execute("ALTER TABLE bookings_new RENAME TO bookings")
    conn.commit()
    print('Migration complete: bookings table replaced. Old table renamed to bookings_old')
except Exception as e:
    print('Migration failed:', e)
    conn.rollback()

conn.close()
