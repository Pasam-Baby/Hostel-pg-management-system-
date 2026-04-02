from flask_mail import Mail, Message
from flask import current_app
from threading import Thread

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Error sending email: {e}")

def send_email(to, subject, template):
    # Only attempt to send if email is configured
    if not current_app.config.get('MAIL_USERNAME'):
        print(f"Mock Email to {to} [Subject: {subject}]")
        print(template)
        return

    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=current_app.config.get('MAIL_DEFAULT_SENDER')
    )
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
