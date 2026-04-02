import requests
url = 'http://127.0.0.1:5000/payment/book/BK9999'
resp = requests.post(url, data={'amount':'1000'})
print('status', resp.status_code)
print(resp.url)
print(resp.text[:400])
