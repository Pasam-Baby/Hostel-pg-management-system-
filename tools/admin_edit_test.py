from hostel_pg_management.app import create_app

app = create_app()
app.testing = True
with app.test_client() as c:
    # Login as admin
    rv = c.get('/admin_login')
    # get csrf token from login page if present
    from bs4 import BeautifulSoup
    html = rv.get_data(as_text=True)
    soup = BeautifulSoup(html, 'html.parser')
    token_input = soup.find('input', {'name': 'csrf_token'})
    token = token_input['value'] if token_input else None

    login_data = {'username': 'admin', 'password': 'admin123'}
    if token:
        login_data['csrf_token'] = token
    r = c.post('/admin_login', data=login_data, follow_redirects=True)
    print('Login status code:', r.status_code)
    # Get admin rooms page to fetch CSRF for edit form
    r = c.get('/admin/rooms')
    print('Rooms page status:', r.status_code)
    soup = BeautifulSoup(r.get_data(as_text=True), 'html.parser')
    form = soup.find('form', {'class': 'admin-edit-form'})
    if not form:
        print('No admin edit form found on rooms page')
    else:
        room_id = form.get('data-room-id')
        token_input = form.find('input', {'name': 'csrf_token'})
        token = token_input['value'] if token_input else None
        print('Found edit form for room id', room_id, 'csrf:', bool(token))
        # submit update
        data = {'sharing_type': '2', 'ac_type': 'AC', 'price': '7777'}
        if token:
            data['csrf_token'] = token
        resp = c.post(f'/admin/api/update_room/{room_id}', data=data)
        print('Update response code:', resp.status_code)
        try:
            print('JSON:', resp.get_json())
        except Exception:
            print('Response text:', resp.get_data(as_text=True))
