import sqlite3
import os

db_path = 'hostel_pg_management/hostel.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("Tables:", tables)
    for table in tables:
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
        print(f"  {table}: {cols}")
    conn.close()
else:
    print("DB not found")
