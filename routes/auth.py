"""Registration, login, email verification and logout (customer portal + gym admin portal)."""
import re
import smtplib
import socket
import time
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from db import query, execute, commit, rollback
from models import User, Customer, Admin, Gym
from utils.mailer import send_login_code, send_reset_code, hash_code, mail_is_configured
from utils.security import home_for
from utils.ph_address import read_address

auth = Blueprint("auth", __name__)
admin_auth = Blueprint("admin_auth", __name__, url_prefix="/admin")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^09\d{9}$")   # Philippines mobile: 09 + 9 digits (11 digits)
PHONE_MSG = "Contact number must be a Philippine mobile number: 11 digits starting with 09 (example 09171234567)."


def _valid_password(pw, confirm):
    if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must be at least 8 characters with letters and numbers."
    if pw != confirm:
        return "Passwords do not match."
    return None


def _start_verification(user, portal):
    """Send the email code and go to the verify page."""
    try:
        dev_code = send_login_code(user)
    except Exception as exc:
        rollback()
        print("\n[EMAIL ERROR]", type(exc).__name__, "-", exc, "\n")   # the real reason shows in your terminal
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            why = "Gmail rejected the email or App Password. Create a new App Password and paste it in .env (16 letters, no spaces)."
        elif isinstance(exc, (smtplib.SMTPConnectError, socket.gaierror, TimeoutError, ConnectionError, OSError)):
            why = "Could not reach Gmail. Check your internet, or a firewall/antivirus blocking port 587."
        else:
            why = "Check the MAIL settings in your .env file."
        flash("We could not send the email. " + why, "danger")
        return None
    session.clear()
    session["pending_user_id"] = user.id
    session["pending_portal"] = portal
    session["verify_attempts"] = 0
    if dev_code:
        session["dev_code"] = dev_code
    return redirect(url_for("auth.verify"))


def _after_register(uid, portal, login_endpoint):
    """New account: email a 6-digit code to confirm the email, then they log in on the verify page."""
    user = User.find_by_id(uid)
    resp = _start_verification(user, portal)
    if resp:
        flash("Account created! We sent a 6-digit code to your email. Enter it to confirm your email and log in.", "success")
        return resp
    flash("Account created! Log in to receive your email code.", "success")
    return redirect(url_for(login_endpoint))


# ---------------------------------------------------------------- customer
@auth.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user"):
        return redirect(home_for(g.user))
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in
             ("first_name", "middle_name", "last_name", "dob", "contact", "email")}
        addr, addr_error = read_address(request.form)
        f.update(addr)
        f["contact"] = re.sub(r"[\s-]", "", f["contact"])
        pw, confirm = request.form.get("password", ""), request.form.get("confirm", "")
        error = None
        if not (f["first_name"] and f["last_name"]):
            error = "Please fill in your name."
        elif not EMAIL_RE.match(f["email"]):
            error = "Enter a valid email address."
        elif not PHONE_RE.match(f["contact"]):
            error = PHONE_MSG
        elif addr_error:
            error = addr_error
        else:
            try:
                born = datetime.strptime(f["dob"], "%Y-%m-%d").date()
                if born >= date.today():
                    raise ValueError
            except ValueError:
                error = "Enter a valid date of birth."
        error = error or _valid_password(pw, confirm)
        if not error and User.find_by_email(f["email"]):
            error = "That email is already registered."
        if error:
            flash(error, "danger")
            return render_template("auth/register.html", f=f)
        try:
            uid = User.create(f["email"], pw, "customer")
            Customer.create_profile(uid, f["first_name"], f["middle_name"], f["last_name"], born, f["contact"], f["full"])
            commit()
        except Exception:
            rollback()
            flash("Could not create your account. Please try again.", "danger")
            return render_template("auth/register.html", f=f)
        return _after_register(uid, "customer", "auth.login")
    return render_template("auth/register.html", f={})


@auth.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(home_for(g.user))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.find_by_email(email)
        if not user or not user.is_active or not user.check_password(request.form.get("password", "")):
            flash("Invalid email or password.", "danger")
        elif user.role != "customer":
            flash("That is a gym admin account. Please use the Gym Owner login.", "warning")
        else:
            resp = _start_verification(user, "customer")
            if resp:
                return resp
    return render_template("auth/login.html")


@auth.route("/verify", methods=["GET", "POST"])
def verify():
    uid = session.get("pending_user_id")
    if not uid:
        return redirect(url_for("auth.login"))
    user = User.find_by_id(uid)
    portal = session.get("pending_portal", "customer")
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        session["verify_attempts"] = session.get("verify_attempts", 0) + 1
        if session["verify_attempts"] > 5:
            session.clear()
            flash("Too many wrong codes. Please log in again.", "danger")
            return redirect(url_for("admin_auth.admin_login" if portal == "admin" else "auth.login"))
        code = request.form.get("code", "").strip()
        token = query("SELECT * FROM email_verification_tokens WHERE user_id=%s AND token_hash=%s AND used_at IS NULL",
                      (user.id, hash_code(code)), one=True)
        if not token or token["expires_at"] < datetime.utcnow():
            flash("Wrong or expired code.", "danger")
        else:
            execute("UPDATE email_verification_tokens SET used_at=%s WHERE id=%s", (datetime.utcnow(), token["id"]))
            User.mark_verified(user.id)
            commit()
            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            flash(f"Welcome, {user.full_name}!", "success")
            return redirect(home_for(user))
    return render_template("auth/verify.html", email=user.email, portal=portal,
                           dev_code=session.get("dev_code"), mail_ok=mail_is_configured())


@auth.route("/resend-code", methods=["POST"])
def resend_code():
    uid = session.get("pending_user_id")
    user = User.find_by_id(uid) if uid else None
    if not user:
        return redirect(url_for("auth.login"))
    portal = session.get("pending_portal", "customer")
    resp = _start_verification(user, portal)
    if resp:
        flash("A new code was sent.", "success")
        return resp
    return redirect(url_for("auth.verify"))


# ---------------------------------------------------------------- forgot password
def _email_failed(exc):
    rollback()
    print("\n[EMAIL ERROR]", type(exc).__name__, "-", exc, "\n")
    flash("We could not send the email. Check the MAIL settings in your .env file.", "danger")


def _send_reset(user):
    """Email a reset code. Returns True when sent (or shown in dev mode)."""
    try:
        code = send_reset_code(user)
    except Exception as exc:
        _email_failed(exc)
        return False
    session["reset_dev_code"] = code
    session["reset_sent_at"] = time.time()
    return True


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if g.get("user"):
        return redirect(home_for(g.user))
    portal = request.values.get("portal", "customer")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not EMAIL_RE.match(email):
            flash("Enter a valid email address.", "danger")
        else:
            user = User.find_by_email(email)
            session.pop("reset_user_id", None)
            session.pop("reset_dev_code", None)
            session["reset_email"] = email
            session["reset_portal"] = "admin" if (user and user.role == "admin") else "customer"
            session["reset_attempts"] = 0
            if user and user.is_active:
                if not _send_reset(user):
                    return render_template("auth/forgot.html", portal=portal)
                session["reset_user_id"] = user.id
            # Same message whether or not the email is registered (so nobody can probe for accounts).
            flash("If that email is registered, we sent a 6-digit code to it.", "success")
            return redirect(url_for("auth.reset_password"))
    return render_template("auth/forgot.html", portal=portal)


@auth.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if g.get("user"):
        return redirect(home_for(g.user))
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))
    portal = session.get("reset_portal", "customer")
    if request.method == "POST":
        session["reset_attempts"] = session.get("reset_attempts", 0) + 1
        if session["reset_attempts"] > 5:
            for k in ("reset_email", "reset_user_id", "reset_dev_code", "reset_portal", "reset_attempts"):
                session.pop(k, None)
            flash("Too many wrong codes. Please start again.", "danger")
            return redirect(url_for("auth.forgot_password"))
        code = request.form.get("code", "").strip()
        problem = _valid_password(request.form.get("password", ""), request.form.get("confirm", ""))
        uid = session.get("reset_user_id")
        token = query("SELECT * FROM password_reset_tokens WHERE user_id=%s AND token_hash=%s AND used_at IS NULL",
                      (uid, hash_code(code)), one=True) if uid else None
        if not token or token["expires_at"] < datetime.utcnow():
            flash("Wrong or expired code.", "danger")
        elif problem:
            flash(problem, "danger")
        else:
            user = User.find_by_id(uid)
            user.set_password(request.form.get("password", ""))
            execute("UPDATE password_reset_tokens SET used_at=%s WHERE user_id=%s", (datetime.utcnow(), uid))
            commit()
            for k in ("reset_email", "reset_user_id", "reset_dev_code", "reset_portal", "reset_attempts", "reset_sent_at"):
                session.pop(k, None)
            flash("Your password was changed. Log in with your new password.", "success")
            return redirect(url_for("admin_auth.admin_login" if user.role == "admin" else "auth.login"))
    return render_template("auth/reset.html", email=email, portal=portal,
                           dev_code=session.get("reset_dev_code"), mail_ok=mail_is_configured())


@auth.route("/reset-password/resend", methods=["POST"])
def resend_reset():
    uid = session.get("reset_user_id")
    user = User.find_by_id(uid) if uid else None
    if user:
        if time.time() - session.get("reset_sent_at", 0) < 30:
            flash("Please wait 30 seconds before asking for another code.", "danger")
        elif _send_reset(user):
            session["reset_attempts"] = 0
            flash("A new code was sent.", "success")
    elif session.get("reset_email"):
        flash("If that email is registered, a new code was sent.", "success")
    return redirect(url_for("auth.reset_password") if session.get("reset_email") else url_for("auth.forgot_password"))


@auth.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))


# ---------------------------------------------------------------- gym admin
@admin_auth.route("/register", methods=["GET", "POST"])
def admin_register():
    if g.get("user"):
        return redirect(home_for(g.user))
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in
             ("first_name", "last_name", "contact", "email", "gym_name")}
        addr, addr_error = read_address(request.form)
        f.update(addr)
        f["contact"] = re.sub(r"[\s-]", "", f["contact"])
        pw, confirm = request.form.get("password", ""), request.form.get("confirm", "")
        error = None
        if not all([f["first_name"], f["last_name"], f["gym_name"]]):
            error = "Please fill in all required fields."
        elif not EMAIL_RE.match(f["email"]):
            error = "Enter a valid email address."
        elif not PHONE_RE.match(f["contact"]):
            error = PHONE_MSG
        elif addr_error:
            error = addr_error
        error = error or _valid_password(pw, confirm)
        if not error and User.find_by_email(f["email"]):
            error = "That email is already registered."
        if error:
            flash(error, "danger")
            return render_template("admin/register.html", f=f)
        try:
            uid = User.create(f["email"], pw, "admin")
            gym_id = Gym.create(f["gym_name"], f["detail"], f["city"], f["province"], f["contact"], f["email"])
            Admin.create_profile(uid, gym_id, f["first_name"], f["last_name"], f["contact"])
            commit()
        except Exception:
            rollback()
            flash("Could not create the gym account. Please try again.", "danger")
            return render_template("admin/register.html", f=f)
        return _after_register(uid, "admin", "admin_auth.admin_login")
    return render_template("admin/register.html", f={})


@admin_auth.route("/login", methods=["GET", "POST"])
def admin_login():
    if g.get("user"):
        return redirect(home_for(g.user))
    if request.method == "POST":
        user = User.find_by_email(request.form.get("email", "").strip())
        if not user or not user.is_active or not user.check_password(request.form.get("password", "")):
            flash("Invalid email or password.", "danger")
        elif user.role != "admin":
            flash("That is a customer account. Please use the customer login.", "warning")
        else:
            resp = _start_verification(user, "admin")
            if resp:
                return resp
    return render_template("admin/login.html")
