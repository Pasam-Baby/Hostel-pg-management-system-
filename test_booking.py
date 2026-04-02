import urllib.request, urllib.parse, re, traceback, http.cookiejar

BASE = 'http://127.0.0.1:5000'

# preserve cookies (session for CSRF)
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(url):
    req = urllib.request.Request(url)
    with opener.open(req, timeout=10) as r:
        return r.read().decode('utf-8', 'replace')


def post(url, data):
    data_bytes = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=data_bytes)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with opener.open(req, timeout=15) as r:
            return r.getcode(), r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        # return the status and body from the error response (useful to inspect tracebacks)
        try:
            body = e.read().decode('utf-8', 'replace')
        except Exception:
            body = ''
        return e.code, body


try:
    print('Fetching /book to locate an available room...')
    body = get(BASE + '/book')
    m = re.search(r'\?room_id=(\d+)', body)
    if not m:
        print('No room link found on /book')
        exit(1)
    room_id = m.group(1)
    print('Found room_id=', room_id)

    print(f'Opening booking page for room {room_id}...')
    page = get(BASE + f'/book?room_id={room_id}')
    # try to extract csrf_token and hidden fields
    csrf = None
    m_csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', page)
    if m_csrf:
        csrf = m_csrf.group(1)
        print('Found csrf_token')
    else:
        print('No csrf_token found (proceeding without it)')

    def find_hidden(name):
        mm = re.search(r'name="%s"\s+value="([^"]+)"' % re.escape(name), page)
        return mm.group(1) if mm else ''

    sharing_type = find_hidden('sharing_type')
    ac_type = find_hidden('ac_type')
    print('sharing_type=', sharing_type, 'ac_type=', ac_type)

    data = {
        'room_id': room_id,
        'name': 'Test User',
        'phone': '9999999999',
        'email': 'test+bot@example.com',
        'address': 'Test address',
        'password': 'Pass1234',
        'confirm_password': 'Pass1234',
        'sharing_type': sharing_type,
        'ac_type': ac_type,
    }
    if csrf:
        data['csrf_token'] = csrf

    print('Submitting booking form...')
    status, resp = post(BASE + '/book', data)
    print('POST status=', status)
    print('Response snippet:\n', resp[:1000])

except Exception:
    traceback.print_exc()
