import sqlite3
DB = r'C:/Users/hp/OneDrive/Desktop/hostel_pg_management (5)/hostel_pg_management/hostel.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
row = cur.execute('SELECT id,name,email,phone,visit_date,visit_time,status,created_at FROM visits ORDER BY id DESC LIMIT 1').fetchone()
if row:
    print('VISIT:', row['id'], row['name'], row['email'], row['visit_date'], row['visit_time'], row['status'])
else:
    print('NO_VISITS')
conn.close()
