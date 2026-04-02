import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = {
    "food_menu_bg.jpg": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=1600&h=900&fit=crop",
    "facilities_bg.jpg": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&h=900&fit=crop"
}

for name, url in urls.items():
    print(f"Downloading {name}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx) as response, open(f"hostel_pg_management/static/images/{name}", 'wb') as out_file:
        out_file.write(response.read())
print("Done!")
