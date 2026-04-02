# Secure Web-Based Hostel & PG Management System

**Updated Project Title:** Hostel & PG Management System

Welcome to the **Secure Web-Based Hostel & PG Management System**, a dynamic, feature-rich platform developed to streamline the administration and day-to-day operations of hostels and paying guest (PG) accommodations. Built on a robust tech stack securely implemented using industry-standard practices, this project is perfect for managing tenant records, financial transactions, room allocators, and complaint ticketing.

## 📖 Table of Contents
- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Installation Guide](#-installation-guide)
- [Project Configuration](#-project-configuration)
- [Usage (Local Environment)](#-usage-local-environment)
- [Deployment Configuration](#-deployment-configuration)
- [Future Scope](#-future-scope)

## ✨ Features

### 👤 Admin Module
- **Dashboard Analytics:** Visual interpretation of active students, available rooms, pending complaints, and total revenue using **Chart.js** integration.
- **Room Management:** Comprehensive CRUD operations to define room capacities. Over-allocation prevention logic strictly enforced.
- **Student Roster Management:** Secure enrollment workflow using SHA-256 hashed credentials.
- **Financial Ticketing System:** Monitor incoming payments alongside a consolidated Complaints resolution tracker.
- **PDF Report Generation:** Generate and download official Roster, Payment History, and Complaints reports dynamically constructed via **ReportLab**.

### 🎓 Student Module
- **Self-Service Dashboard:** Review room allocations, payment history, and complaint status metrics.
- **Digital Receipts:** Extract transaction proofs effortlessly in PDF format.
- **Support Workflows:** Ability to formally document issues within the hostel environment straight to administration in real time.
- **Profile Configuration:** Effortlessly update contact protocols and refresh cryptographic hashes tied to your identity.

### 🛡️ Security Embellishments
- **Cryptographic Algorithms:** Strict implementation of `werkzeug.security` routines ensuring password matrices resist dictionary or rainbow table attacks over the SQLite footprint.
- **CSRF Tokenization:** Stateful prevention of Cross-Site Request Forgery maneuvers by intertwining `Flask-WTF` validation across all POST transactions.
- **Environment Isolation:** Abstracting connection boundaries and operational keys behind `.env` enclosures.
- **SQL Injection Prevention:** Enforced usage of parameterized query mappings across the entire database integration layer.

## � New Features Added

### 🌙 Dark Mode Toggle
- **UI Enhancement:** Professional dark/light mode toggle button in navigation
- **Persistence:** User preference saved using localStorage
- **Complete Theme:** Dark backgrounds, light text, updated cards, forms, and UI elements
- **Smooth Transitions:** Professional animations and hover effects

### 📢 Notice Board System
- **Admin Features:** Add and delete hostel notices/announcements
- **Student Access:** View-only access to all notices
- **Database:** Separate SQLite database (`notice.db`) for notice management
- **UI:** Clean card-based layout with timestamps and professional styling

### 🛏️ Booking & Visit Expansion
- **Room Booking:** Dynamic rent calculation with integrated late fee tracking.
- **Visit Scheduling:** Interface for prospective tenants to schedule site visits.
- **Admin Sync:** Seamless UI updates ensuring admin room changes reflect immediately on public pages.

## 📸 Screenshots

*Updated UI screenshots including Dark Mode and Notice Board features will be added here.*

- **Light Mode Dashboard:** Clean, professional interface with Chart.js analytics
- **Dark Mode Dashboard:** Enhanced user experience with dark theme
- **Notice Board:** Admin interface for managing announcements
- **Student Portal:** Notice viewing interface for students
## �🏗️ System Architecture

The ecosystem relies on an MVC-oriented (Model-View-Controller) topology.

1. **View (Frontend):** Composed of Jinja2 rendered HTML templates extensively adorned with **Bootstrap 5** for mobility-first reactivity. Retains immutable aesthetic background matrices.
2. **Controller (Application Logic):** Directed by Python Flask Blueprints isolating Administrative constructs from Student realms.
3. **Model (Database Layer):** SQLite3 file-system encapsulation (`hostel.db`).

## 💻 Technology Stack

* **Backend Development:** Python 3, Flask framework
* **Database Management:** SQLite3 (Main: `hostel.db`, Notices: `notice.db`)
* **Frontend Design:** HTML5, CSS3, JavaScript, Bootstrap 5
* **Security Subsystems:** Flask-WTF (CSRF Protection), Authlib, Werkzeug
* **Data Visualization:** Chart.js
* **UI Enhancements:** JavaScript (Dark Mode, Interactive Features)
* **Document Genesis:** ReportLab (PDF Synthesis)

## ⚙️ Installation Guide

Follow these steps to reconstruct the environment locally.

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/hostel_pg_management.git
   cd hostel_pg_management
   ```

2. **Initialize Virtual Environment (Optional but Recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate       # macOS/Linux
   .venv\Scripts\activate          # Windows
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🔐 Project Configuration

Create a `.env` file in the root directory to define the isolation boundaries:

```env
SECRET_KEY=generate_a_strong_random_key
FLASK_APP=app.py
FLASK_ENV=development

# SMTP Setup for Email Functionality
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
```

## 🚀 Usage (Local Environment)

Bootstrapping the system is accomplished in a single command. The system automatically initializes the SQLite schema (`hostel.db`) yielding a singular default admin user.

```bash
python app.py
```

* Ensure connection over `http://127.0.0.1:5000`
* Default Administrator Credentials:
  * **Username:** `admin`
  * **Password:** `admin123`

## ☁️ Deployment Configuration

The repository contains `Procfile` mapping for WSGI compliant distribution arrays standard across PaaS ecosystems like Heroku. Ensure Python instances match defined prerequisites.

```text
web: gunicorn app:app
```

## 🔮 Future Scope
* Implantation of active payment gateways (Stripe/RazorPay).
* Live notification architecture via WebSockets.
* Progressive Web App (PWA) manifest adoption.
* Mobile responsiveness improvements for enhanced user experience.
* Advanced analytics dashboard with detailed reporting metrics.
* Push notification system for important announcements and updates.

---
_Designed and developed as part of a final-year academic curriculum projection._
