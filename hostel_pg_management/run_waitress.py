from waitress import serve
from app import create_app

if __name__ == "__main__":
    app = create_app()
    print("🚀 Starting Production WSGI Server on http://127.0.0.1:5000 using Waitress...")
    serve(app, host='127.0.0.1', port=5000)
