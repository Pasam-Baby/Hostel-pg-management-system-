import os
import json
import urllib.request


def send_sms(phone: str, message: str) -> bool:
    """Send SMS using an external HTTP provider if configured by env var SMS_API_URL.
    If no provider configured, log to server_sms.log as a fallback (simulates sending).
    Returns True if message was queued/sent (best-effort).
    """
    phone = phone or ''
    message = message or ''
    api_url = os.environ.get('SMS_API_URL')
    api_key = os.environ.get('SMS_API_KEY')

    if api_url:
        try:
            payload = json.dumps({'phone': phone, 'message': message}).encode('utf-8')
            req = urllib.request.Request(api_url, data=payload, headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-KEY': api_key or ''
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.getcode()
                return 200 <= status < 300
        except Exception:
            # fallthrough to logging
            pass

    try:
        with open('server_sms.log', 'a', encoding='utf-8') as fh:
            fh.write(f"SMS to {phone}: {message}\n")
        return True
    except Exception:
        return False
