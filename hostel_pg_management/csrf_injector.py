import os
import re

template_dir = r"c:\Users\hp\OneDrive\Desktop\hostel_pg_management (5)\hostel_pg_management\templates"
csrf_tag = '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">'

for root, _, files in os.walk(template_dir):
    for f in files:
        if f.endswith(".html"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            # Replace forms
            new_content = re.sub(r'(<form[^>]*)>', r'\1>' + csrf_tag, content)
            
            if new_content != content:
                with open(path, "w", encoding="utf-8") as file:
                    file.write(new_content)
                print(f"Updated {f}")
