from werkzeug.security import generate_password_hash
import sqlite3

con = sqlite3.connect("hostel.db")
cur = con.cursor()

cur.execute(
    "INSERT OR IGNORE INTO admin (username, password) VALUES (?, ?)",
    ("admin", generate_password_hash("admin123"))
)

con.commit()
con.close()
