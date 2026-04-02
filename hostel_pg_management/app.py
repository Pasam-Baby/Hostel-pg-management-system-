from flask import Flask, render_template, session
from hostel_pg_management.config import Config
from flask_wtf.csrf import CSRFProtect
from hostel_pg_management.utils.mail import mail
from hostel_pg_management.utils.oauth import oauth

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    csrf.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)
    
    # Configure Google OAuth Profile
    try:
        oauth.register(
            name='google',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
    except Exception as e:
        print("Warning: Google OAuth failed to initialize cleanly.", e)

    # Initialize database teardown and schema
    from hostel_pg_management.database.db import close_db, init_db
    app.teardown_appcontext(close_db)

    # Ensure DB schema exists (safe to call multiple times)
    # This guarantees tables like `facilities` and `notices` are present
    import os
    from hostel_pg_management.config import Config as _Config
    db_path = _Config.DATABASE
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            print("Warning: init_db failed:", e)

    # Register Blueprints (use package-qualified imports)
    from hostel_pg_management.routes.auth import auth_bp
    from hostel_pg_management.routes.admin import admin_bp
    from hostel_pg_management.routes.student import student_bp
    from hostel_pg_management.routes.booking import booking_bp
    from hostel_pg_management.routes.payment import payment_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(booking_bp)
    app.register_blueprint(payment_bp)

    # Register Report Blueprint
    from hostel_pg_management.routes.report import report_bp
    app.register_blueprint(report_bp, url_prefix='/admin/report')

    # Register Recovery Blueprint
    from hostel_pg_management.routes.recovery import recovery_bp
    app.register_blueprint(recovery_bp)

    # Register Notice Blueprint (notices stored in main DB)
    from hostel_pg_management.routes.notice import notice_bp
    app.register_blueprint(notice_bp, url_prefix='/notice')

    @app.context_processor
    def inject_notifications():
        from hostel_pg_management.database.db import get_db
        db = get_db()
        notes = []
        emergency_number = "+91 98765 40000"
        try:
            if session.get('student_id'):
                # show both student-specific and public notifications
                notes = db.execute(
                    "SELECT * FROM notifications WHERE is_read=0 AND (user_type='public' OR (user_type='student' AND user_id=?)) ORDER BY created_at DESC LIMIT 5",
                    (session['student_id'],),
                ).fetchall()
            elif session.get('admin'):
                notes = db.execute(
                    "SELECT * FROM notifications WHERE is_read=0 ORDER BY created_at DESC LIMIT 5"
                ).fetchall()
            # fetch emergency number from settings if present
            try:
                row = db.execute("SELECT value FROM settings WHERE key='emergency_number'").fetchone()
                if row and row['value']:
                    emergency_number = row['value']
            except Exception:
                pass
        except Exception:
            notes = []
        return dict(notifications=notes, emergency_number=emergency_number)

    @app.route("/")
    def home():
        from hostel_pg_management.database.db import get_db as get_main_db
        db = get_main_db()
        rooms = db.execute(
            """
            SELECT room_no, sharing_type, ac_type, total_beds, available_beds, price, status
            FROM rooms
            ORDER BY sharing_type, ac_type, room_no
            """
        ).fetchall()
        price_table = [
            {"sharing_type": 1, "ac_type": "AC", "price": 9000},
            {"sharing_type": 1, "ac_type": "Non-AC", "price": 6000},
            {"sharing_type": 2, "ac_type": "AC", "price": 7500},
            {"sharing_type": 2, "ac_type": "Non-AC", "price": 6000},
            {"sharing_type": 3, "ac_type": "AC", "price": 6500},
            {"sharing_type": 3, "ac_type": "Non-AC", "price": 5500},
            {"sharing_type": 4, "ac_type": "AC", "price": 6000},
            {"sharing_type": 4, "ac_type": "Non-AC", "price": 5000},
        ]
        # Load weekly food menu from DB if available
        try:
            dbm = get_main_db()
            fm_rows = dbm.execute('SELECT day, breakfast, lunch, dinner FROM food_menu ORDER BY id').fetchall()
            if fm_rows:
                food_menu = [dict(day=r['day'], breakfast=r['breakfast'], lunch=r['lunch'], dinner=r['dinner']) for r in fm_rows]
            else:
                food_menu = []
            fac_rows = dbm.execute('SELECT name, description FROM facilities ORDER BY id').fetchall()
            facilities = [dict(name=f['name'], description=f['description']) for f in fac_rows] if fac_rows else []
        except Exception:
            food_menu = []
            facilities = []

        gallery_images = [
            "images/landing.png",
            "images/rooms_bg.png",
            "images/facilities_bg.jpg",
            "images/food_menu_bg.jpg",
        ]
        return render_template(
            "index.html",
            rooms=rooms,
            price_table=price_table,
            food_menu=food_menu,
            gallery_images=gallery_images,
            emergency_number="+91 98765 40000",
            facilities=facilities,
        )

    return app

app = create_app()

if __name__ == "__main__":
    # If run directly
    app.run(debug=True, host='0.0.0.0', port=5000)
