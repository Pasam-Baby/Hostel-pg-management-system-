import sqlite3
DB = r'C:/Users/hp/OneDrive/Desktop/hostel_pg_management (5)/hostel_pg_management/hostel.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()
cols=[c[1] for c in cur.execute('PRAGMA table_info(bookings)').fetchall()]
if 'address' not in cols:
    cur.execute('ALTER TABLE bookings ADD COLUMN address TEXT')
    print('added address')
if 'password_hash' not in cols:
    cur.execute('ALTER TABLE bookings ADD COLUMN password_hash TEXT')
    print('added password_hash')
conn.commit()
conn.close()
