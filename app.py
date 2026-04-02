from os import environ
import logging

# Ensure package is importable when running from repository root
try:
    from hostel_pg_management.app import create_app
except Exception as e:
    # Provide a helpful error if import fails
    logging.error("Failed to import create_app from hostel_pg_management.app: %s", e)
    raise

app = create_app()

if __name__ == "__main__":
    # Default host/port to 127.0.0.1:5000 to match user's requirement
    host = environ.get('HOST', '127.0.0.1')
    port = int(environ.get('PORT', 5000))
    # Use debug mode when environment variable DEBUG is set to '1'
    debug = environ.get('DEBUG', '1') == '1'
    app.run(debug=debug, host=host, port=port)
