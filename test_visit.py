import requests, time
from datetime import datetime, timedelta
base='http://127.0.0.1:5000'
# Give server a moment
import sys
import time
for _ in range(5):
    try:
        r = requests.get(base+'/')
        break
    except Exception:
        time.sleep(1)
# Create a test student via registration endpoint
s = requests.Session()
reg = s.post(base+'/student_register', data={'name':'Test Student','email':'test_student@example.com','phone':'9999999999','password':'pass123','room_id':''}, allow_redirects=False)
print('reg', reg.status_code)
# Attempt login
login = s.post(base+'/student_login', data={'email':'test_student@example.com','password':'pass123'}, allow_redirects=False)
print('login', login.status_code)
# Schedule a visit

dt = datetime.now() + timedelta(days=1)
visit_date = dt.strftime('%Y-%m-%d')
visit_time = dt.strftime('%H:%M')
resp = s.post(base+'/schedule_visit', data={'name':'Visitor X','relation':'Father','email':'visitorx@example.com','phone':'8888888888','visit_date':visit_date,'visit_time':visit_time}, allow_redirects=True)
print('schedule status', resp.status_code)
# Fetch student visits page
vis = s.get(base+'/student/visits')
print('student visits page', vis.status_code, 'contains Visitor X?', 'Visitor X' in vis.text)
# Fetch admin visits (need admin login)
s_admin = requests.Session()
admin_login = s_admin.post(base+'/admin_login', data={'username':'admin','password':'admin123'}, allow_redirects=False)
print('admin login', admin_login.status_code)
admin_vis = s_admin.get(base+'/admin/visits')
print('admin visits page', admin_vis.status_code, 'contains Visitor X?', 'Visitor X' in admin_vis.text)
