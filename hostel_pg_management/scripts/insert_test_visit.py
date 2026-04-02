import sqlite3
from datetime import datetime

DB = r'C:/Users/hp/OneDrive/Desktop/hostel_pg_management (5)/hostel_pg_management/hostel.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("INSERT INTO visits (name,email,phone,visit_date,visit_time,status) VALUES (?,?,?,?,?,?)", (
    'Automation Tester', 'auto@test.local', '9999999999', '2026-04-03', '14:30', 'Pending'
))
conn.commit()
print('VISIT_INSERTED')
conn.close()
