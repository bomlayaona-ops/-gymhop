"""Email login codes (6 digits, valid 5 minutes)."""
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import current_app
from flask_mail import Message
from extensions import mail
from db import execute


def _hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


def hash_code(code):
    return _hash(code)


def mail_is_configured():
    cfg = current_app.config
    return bool(cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))


def _send_code(user, table, subject, intro, ignore_line):
    """Create a 6-digit code (valid 5 minutes), save only its hash in `table`, and email it.
    Returns the code ONLY in dev mode (when no email account is set up yet)."""
    from db import commit
    code = f"{secrets.randbelow(1000000):06d}"
    execute(f"DELETE FROM {table} WHERE user_id=%s AND used_at IS NULL", (user.id,))
    execute(f"INSERT INTO {table} (user_id, token_hash, expires_at) VALUES (%s,%s,%s)",
            (user.id, _hash(code), datetime.utcnow() + timedelta(minutes=5)))
    commit()
    if not mail_is_configured():
        current_app.logger.warning("DEV MODE: email is not set up. Code for %s is %s", user.email, code)
        return code
    msg = Message(
        subject=subject,
        recipients=[user.email],
        body=(f"Hi {user.full_name},\n\n{intro}\n\nYour GymHop code is: {code}\n\n"
              f"It expires in 5 minutes. {ignore_line}\n\n- GymHop"),
        html=(f"<div style='font-family:Arial;max-width:480px;margin:auto;padding:24px;background:#111;color:#fff;border-radius:12px'>"
              f"<h2 style='color:#e50914;margin:0 0 8px'>GymHop</h2><p>Hi {user.full_name}, {intro}</p>"
              f"<p style='font-size:34px;letter-spacing:8px;font-weight:800;margin:18px 0'>{code}</p>"
              f"<p style='color:#aaa;font-size:12px'>It expires in 5 minutes. {ignore_line}</p></div>"),
    )
    mail.send(msg)
    return None


def send_login_code(user):
    return _send_code(user, "email_verification_tokens", "Your GymHop login code",
                      "use this code to finish logging in.", "If you did not try to log in, please ignore this email.")


def send_reset_code(user):
    return _send_code(user, "password_reset_tokens", "Reset your GymHop password",
                      "use this code to reset your password.", "If you did not ask to reset your password, ignore this email and your password stays the same.")
