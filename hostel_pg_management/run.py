import sys, os
# Ensure the parent directory is on PYTHONPATH so absolute imports work when run as a script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from hostel_pg_management.app import create_app
from hostel_pg_management.database.db import init_db
from hostel_pg_management.config import Config
import os

if __name__ == '__main__':
    # Automatically initialize DB if it doesn't exist (use configured path)
    db_path = Config.DATABASE
    if not os.path.exists(db_path):
        init_db()

    # Ensure admin credentials exist and match requested default (Username: Admin, Password: Admin123)
    try:
        import sqlite3
        from werkzeug.security import generate_password_hash

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        admin = cur.execute("SELECT * FROM admin WHERE LOWER(username)=LOWER('admin')").fetchone()
        admin_hash = generate_password_hash('admin123')
        if admin:
            # Update password to the requested default if it doesn't match (best-effort)
            cur.execute("UPDATE admin SET password = ? WHERE LOWER(username)=LOWER('admin')", (admin_hash,))
        else:
            cur.execute("INSERT INTO admin (username, password) VALUES ('admin', ?)", (admin_hash,))
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Create the Flask app via the factory to guarantee all routes are registered.
    app = create_app()

    # Allow overriding port via environment variable (useful in some environments)
    port = int(os.environ.get('PORT', 5000))
    # Bind to all interfaces in case localhost resolution is blocked
    app.run(debug=True, host='0.0.0.0', port=port)
