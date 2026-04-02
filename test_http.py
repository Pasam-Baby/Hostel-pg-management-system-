import urllib.request
import traceback

def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            code = r.getcode()
            body = r.read(1000).decode('utf-8', 'replace')
            print(f"URL: {url} STATUS: {code}\nBODY_SNIPPET:\n{body[:800]}\n---\n")
    except Exception:
        print(f"ERROR fetching {url}")
        traceback.print_exc()

if __name__ == '__main__':
    fetch('http://127.0.0.1:5000')
    fetch('http://127.0.0.1:5000/book')
