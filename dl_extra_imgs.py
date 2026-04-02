import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

images = {
    "food_menu_bg.jpg": "https://images.unsplash.com/photo-1543353071-10c8ba85a904?w=1600&h=900&fit=crop",
    "facilities_bg.jpg": "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=1600&h=900&fit=crop"
}

for name, url in images.items():
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx) as response, open(f"hostel_pg_management/static/images/{name}", 'wb') as out_file:
        out_file.write(response.read())
    print(f"Downloaded {name}")
