import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://images.unsplash.com/photo-1560200353-ce0a76b1d438?w=1600&h=900&fit=crop"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, context=ctx) as response, open("hostel_pg_management/static/images/visit_requests_bg.png", 'wb') as out_file:
    out_file.write(response.read())
print("Downloaded visit_requests_bg.png")
