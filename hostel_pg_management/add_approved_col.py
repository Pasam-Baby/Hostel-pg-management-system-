import sqlite3

def add_approved_column():
    conn = sqlite3.connect('hostel.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(students)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'approved' not in columns:
        print("Adding 'approved' column to 'students' table...")
        cursor.execute("ALTER TABLE students ADD COLUMN approved INTEGER DEFAULT 0")
        conn.commit()
        print("Column added successfully.")
    else:
        print("'approved' column already exists.")
    
    conn.close()

if __name__ == "__main__":
    add_approved_column()
