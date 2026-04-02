import sqlite3

conn = sqlite3.connect('hostel.db')
cursor = conn.cursor()
for table in ['bookings', 'rooms']:
    print(f"--- {table} ---")
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        print(row)
conn.close()
