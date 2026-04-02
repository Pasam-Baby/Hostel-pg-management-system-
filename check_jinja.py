import os
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = r'c:\Users\hp\OneDrive\Desktop\hostel_pg_management (5)\hostel_pg_management\templates'

def check_templates():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    errors = []
    for root, dirs, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith('.html'):
                rel_path = os.path.relpath(os.path.join(root, file), TEMPLATE_DIR)
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        env.parse(f.read())
                    print(f"OK: {rel_path}")
                except Exception as e:
                    print(f"ERROR: {rel_path} - {e}")
                    errors.append((rel_path, str(e)))
    
    if not errors:
        print("\nNo Jinja2 syntax errors found.")
    else:
        print(f"\nFound {len(errors)} Jinja2 syntax errors.")

if __name__ == "__main__":
    check_templates()
