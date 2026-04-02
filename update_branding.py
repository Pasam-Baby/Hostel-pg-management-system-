import os
import re

def replace_in_file(file_path, replacements):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
        # Using regex to replace text while trying to avoid code/variables
        # This is a bit tricky, but for templates, we usually want to replace 
        # text inside tags or titles.
        new_content = re.sub(old, new, new_content)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file_path}")

replacements = {
    r'Active Students': 'Active Residents',
    r'Student Dashboard': 'Resident Dashboard',
    r'User Dashboard': 'Resident Dashboard',
    r'\| Student': '| Resident',
    r'\(Student\)': '(Resident)',
    r'\(User\)': '(Resident)',
    r'User Login': 'Resident Login',
    r'User Logout': 'Resident Logout',
    r'New here\? Register': 'New Resident? Register',
    r'Already have an account\? Login': 'Already a Resident? Login',
    r'Students': 'Residents',
    # Avoid replacing variables like student.id or url_for('student.dashboard')
    # So we only replace 'Student' if it's not preceded by a dot or followed by a dot/underscore
    # Actually, in HTML text, 'Student' is usually just 'Student'.
    r'(?<![.\w])Student(?![.\w])': 'Resident',
    r'(?<![.\w])student(?![.\w])': 'Resident', # Be careful with lowercase
}

template_dir = r'c:\Users\hp\OneDrive\Desktop\hostel_pg_management (5)\hostel_pg_management\templates'

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            replace_in_file(os.path.join(root, file), replacements)
