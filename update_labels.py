import os

template_dir = 'hostel_pg_management/templates'

replacements = {
    "Student Login": "Resident Login",
    "Student Registration": "New Resident Setup",
    "Register as a Student": "Register as a Resident",
    "Student Dashboard": "Resident Dashboard",
    "Total Students": "Total Residents",
    "Active Students": "Active Residents",
    "Students Page": "Residents Page",
    "Student Name": "Resident Name",
    "Student Email": "Resident Email",
    ">Student<": ">Resident<",
    "As a Student": "As a Resident",
    "Admin Login": "Admin Dashboard", # keep mostly as admin
    # "student_login" should not be touched
    # "student_dashboard" should not be touched
}

for root, _, files in os.walk(template_dir):
    for filename in files:
        if filename.endswith('.html'):
            filepath = os.path.join(root, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            for old, new in replacements.items():
                content = content.replace(old, new)
                
            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated: {filename}")
