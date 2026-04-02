import os
import re

template_dir = r"c:\Users\hp\OneDrive\Desktop\hostel_pg_management (5)\hostel_pg_management\templates"

replacements = {
    'students-bg.svg': 'students_bg.png',
    'rooms-bg.svg': 'rooms_bg.png',
    'payments-bg.svg': 'payments_bg.png',
    'complaints-bg.svg': 'complaints_bg.png',
    'announcements-bg.svg': 'announcements_bg.png',
}

def update_templates():
    for filename in os.listdir(template_dir):
        if not filename.endswith('.html'):
            continue
            
        filepath = os.path.join(template_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        
        # We need to find the block page_bg_style and replace 0.4 with 0.82 (very light cover but highly readable)
        # and the SVG filename with PNG filename.
        
        for old_img, new_img in replacements.items():
            if old_img in content:
                # Replace the image
                content = content.replace(old_img, new_img)
                # Replace the transparency overlay to make it lighter/whiter for readability
                # We can use regex to replace rgba(255, 255, 255, 0.4) with rgba(255, 255, 255, 0.85)
                # within the same block.
                # Actually, let's just do a specific replace if we see the old pattern.
                break
                
        # Also replace the overlay for all pages that have an image background in the block
        if "{% block page_bg_style %}" in content and "background-image:" in content:
            content = re.sub(
                r'linear-gradient\(\s*rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*[\d.]+\s*\)\s*,\s*rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*[\d.]+\s*\)\s*\)',
                'linear-gradient(rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.82))',
                content
            )

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filename}")

if __name__ == "__main__":
    update_templates()
