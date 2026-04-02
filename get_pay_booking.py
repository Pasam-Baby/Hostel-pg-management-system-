import requests
r = requests.get('http://127.0.0.1:5000/payment/book/BK9999')
print('status', r.status_code)
print(r.text[:800])
