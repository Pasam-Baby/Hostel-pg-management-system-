import sqlite3

conn = sqlite3.connect('hostel.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables: {tables}")
conn.close()
