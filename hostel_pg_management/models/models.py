from hostel_pg_management.database.db import get_db

class Room:
    @staticmethod
    def get_all():
        db = get_db()
        return db.execute("SELECT * FROM rooms").fetchall()

    @staticmethod
    def get_available():
        db = get_db()
        return db.execute(
            """
            SELECT id, room_no, sharing_type, ac_type, total_beds, available_beds, price
            FROM rooms
            WHERE available_beds > 0
            ORDER BY sharing_type, ac_type, room_no
            """
        ).fetchall()

    @staticmethod
    def update_occupancy(room_id, increment=True):
        db = get_db()
        if increment:
            db.execute(
                """
                UPDATE rooms
                SET occupied = occupied + 1,
                    available_beds = MAX(0, total_beds - (occupied + 1))
                WHERE id = ?
                """,
                (room_id,),
            )
        else:
            db.execute(
                """
                UPDATE rooms
                SET occupied = MAX(0, occupied - 1),
                    available_beds = MIN(total_beds, total_beds - MAX(0, occupied - 1))
                WHERE id = ?
                """,
                (room_id,),
            )
        db.execute(
            """
            UPDATE rooms
            SET status = CASE WHEN available_beds <= 0 THEN 'occupied' ELSE 'available' END
            WHERE id = ?
            """,
            (room_id,),
        )
        db.commit()

class Student:
    @staticmethod
    def get_all():
        db = get_db()
        return db.execute("""
            SELECT students.id, students.name, students.email, students.phone, rooms.room_no, rooms.id as room_id
            FROM students
            LEFT JOIN rooms ON students.room_id = rooms.id
        """).fetchall()

    @staticmethod
    def get_by_id(student_id):
        db = get_db()
        return db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
