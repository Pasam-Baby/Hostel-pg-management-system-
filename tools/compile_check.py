import py_compile, traceback
try:
    py_compile.compile('hostel_pg_management/routes/auth.py', doraise=True)
    print('OK')
except Exception:
    traceback.print_exc()
