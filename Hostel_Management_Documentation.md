# Secure Web-Based Hostel & PG Management System
## Updated Title: Hostel & PG Management System
## Final Year Project Documentation

### 1. Abstract
The "Secure Web-Based Hostel and PG Management System" is a robust, dynamic application designed to automate, streamline, and secure the daily operations of hostels and paying guest (PG) accommodations. Transitioning from traditional, error-prone manual ledgers to an integrated web platform, this system enables real-time administration of room allocation, student data records, financial tracking, and complaint resolution. By incorporating advanced role-based access control, cryptographic password hashing, automated PDF report generation, and third-party Google OAuth integration, the project establishes a highly available and secure environment for both administrators and tenants.

### 2. Introduction
Managing student accommodation requires synchronous tracking of highly volatile data, including rent payments, available bed capacity, and maintenance requests. This project bridges the gap between administrators and tenants by offering dedicated, permission-scoped portals. Administrators are equipped with analytical dashboards, automated occupancy logic, and bulk management tools, while students are granted autonomous oversight of their payments, room details, and direct support lines. The result is a frictionless, transparent, and instantly deployable web solution.

### 3. System Architecture
The application follows a standard Model-View-Controller (MVC) architectural pattern adapted for Flask.

**ER Diagram Design Map:**
- `Admins` (id, username, password, email)
- `Students` (id, name, email `UNIQUE`, password, phone, room_id `FK`, is_verified)
- `Rooms` (id, room_no `UNIQUE`, capacity, occupied, price, ac_type)
- `Complaints` (id, student_id `FK`, subject, complaint, status, created_at)
- `Payments` (id, student_id `FK`, amount, payment_date, status, late_fee)
- `Bookings` (id, booking_id `UNIQUE`, name, phone, email, room_id `FK`, status)
- `Visits` (id, name, email, phone, visit_date, visit_time, status)
- `Notices` (id, title, message, created_at)
- `Food_Menu` (id, day, breakfast, lunch, dinner)
- `Facilities` (id, name, description)
- `Notifications` (id, user_type, user_id, message, is_read)

**Flowchart Navigation:**
1. Authentication Layer (Native / Google OAuth) -> Role Verification
2. Admin Context -> Global Insights, Modifying DB States, Exporting PDFs
3. Student Context -> Local insights, Submitting Queries, Changing Profile

### 4. Modules Explanation
- **Admin Module:** Complete CRUD authority over students, rooms, payments, and complaints. Generates PDF rosters and financial reports. Triggers automated status emails.
- **Student Module:** Read-only access to assigned room statistics and payment history. Ability to initiate support tickets (Complaints) and independently update contact details/passwords. Download PDF receipts.
- **Room Module:** Features an auto-calculating occupancy engine that increments/decrements current capacity dynamically as students are admitted or dropped out, preventing double-booking logic errors.
- **Authentication Module:** Implements layered security consisting of native credential hashing (Werkzeug), encrypted cookie sessions, and external SSO mechanisms (Sign-In with Google) via Authlib.

### 5. Database Design
Built upon an embedded SQLite relational database (`hostel.db`). It enforces referential integrity through Foreign Keys, ensuring orphaned records (e.g., student payments without a student) cannot exist. Strict `UNIQUE` constraints govern critical identifiers like `room_no` and `email`.

### 6. Features List
**Base Features:**
- Separate Admin and Student Login Portals
- Real-time Room Assignment and Capacity Enforcement
- Complaint Status Workflow (Pending -> Resolved)
- Payment Record Keeping

**Advanced Professional Features:**
- Google OAuth Integration
- Cryptographically Secure Forgot Password / Reset Protocol
- Dynamic JS Dashboards (Chart.js)
- Automated PDF Generation (ReportLab) for Invoices and Rosters
- Auto-dispatching Email Notifications
- Advanced Search and Filtering across active databases

### 6.1 Recent Enhancements (2024)

#### 🌙 Dark Mode Implementation
- **UI Enhancement:** Complete dark/light mode toggle functionality
- **Technical Details:** JavaScript-powered theme switching with localStorage persistence
- **User Experience:** Professional dark theme with improved readability and reduced eye strain
- **Implementation:** CSS custom properties for seamless theme transitions

#### 📢 Notice Board System
- **Database Architecture:** Dedicated SQLite database (`notice.db`) for complete data isolation
- **Admin Features:** Full notice management capabilities (Create, Read, Update, Delete operations)
- **Student Interface:** Read-only access with clean, card-based UI design
- **Data Model:** Structured notices table with title, message, timestamp, and admin attribution
- **Security:** Role-based access control ensuring appropriate permissions

#### 🛏️ Room Booking & Visit Scheduling
- **Dynamic Booking:** Public-facing room booking flow with real-time rent and late fee logic.
- **Visit Scheduling:** Prospective residents can schedule site visits directly.
- **Admin Synchronization:** Room details edited by admins instantly sync with the public booking UI.

### 7. Technology Stack Updated
- **Backend:** Python 3.8+, Flask Framework
- **Database:** SQLite3 (Primary: `hostel.db`, Notices: `notice.db`)
- **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5
- **Security:** Flask-WTF (CSRF Protection), Werkzeug (Password Hashing), Authlib (OAuth)
- **Visualization:** Chart.js for interactive dashboards
- **UI Enhancement:** JavaScript for Dark Mode and interactive features
- **PDF Generation:** ReportLab for document creation

### 8. Security Measures
The application is pre-configured for cloud environments (Render, Heroku, Railway).
1. Isolate dependencies: `pip install -r requirements.txt`
2. Define `.env` file with `SECRET_KEY`, `GOOGLE_CLIENT_ID`, etc.
3. Production web-server hook: `gunicorn app:app` (Referenced in `Procfile`).

### 9. Advantages
- Eliminates redundant physical paperwork and human calculation errors.
- Enforces absolute transparency between rent collection and student tracking.
- Massively easily deployable infrastructure carrying low compute overhead.

### 11. Future Enhancements
- Integration of a Live Payment Gateway (e.g., Stripe, Razorpay).
- AI chatbot for generic support queries.
- Facial Recognition integration for physical hostel security checkpoints.
- Mobile responsiveness improvements for enhanced cross-device compatibility.
- Advanced analytics dashboard with detailed reporting and trend analysis.
- Push notification system for real-time announcements and alerts.
