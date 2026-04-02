import sqlite3
from hostel_pg_management.config import Config

conn = sqlite3.connect(Config.DATABASE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('Rooms total:', cur.execute('SELECT COUNT(*) FROM rooms').fetchone()[0])
print('Total occupied:', cur.execute('SELECT SUM(occupied) FROM rooms').fetchone()[0])
print('Total capacity:', cur.execute('SELECT SUM(capacity) FROM rooms').fetchone()[0])
print('Sample students:')
for r in cur.execute('SELECT name,email,room_id FROM students WHERE email LIKE "%@example.com"').fetchall():
    print(' ', r['name'], r['email'], 'room_id', r['room_id'])

conn.close()
