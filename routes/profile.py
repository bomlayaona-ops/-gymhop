"""Profile management for logged-in customers and gym admins: details, email, password and photo."""
import re
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from db import query, commit, rollback
from routes.auth import EMAIL_RE, PHONE_RE, PHONE_MSG, _valid_password
from utils.security import login_required
from utils.uploads import save_image

profile = Blueprint("profile", __name__)


@profile.route("/profile", methods=["GET", "POST"])
@login_required("customer", "admin")
def my_profile():
    user = g.user
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "details":
                _save_details(user)
                flash("Your details were updated.", "success")
            elif action == "email":
                _save_email(user)
                flash("Your email was updated. Use it the next time you log in.", "success")
            elif action == "password":
                _save_password(user)
                flash("Your password was changed.", "success")
            elif action == "photo":
                path = save_image(request.files.get("photo"), "profiles")
                if not path:
                    raise ValueError("Choose a photo first.")
                user.set_photo(path)
                flash("Profile photo updated.", "success")
            elif action == "remove_photo":
                user.set_photo(None)
                flash("Profile photo removed.", "success")
            commit()
            return redirect(url_for("profile.my_profile"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
    return render_template("profile.html", p=user.profile)


def _save_details(user):
    f = {k: request.form.get(k, "").strip() for k in ("first_name", "middle_name", "last_name", "dob", "contact", "address")}
    f["contact"] = re.sub(r"[\s-]", "", f["contact"])
    if not f["first_name"] or not f["last_name"]:
        raise ValueError("First and last name are required.")
    if not PHONE_RE.match(f["contact"]):
        raise ValueError(PHONE_MSG)
    if user.role == "customer":
        if not f["address"]:
            raise ValueError("Address is required.")
        try:
            born = datetime.strptime(f["dob"], "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Enter a valid date of birth.")
        if born >= date.today():
            raise ValueError("Date of birth must be in the past.")
        user.update_profile(f["first_name"], f["middle_name"], f["last_name"], born, f["contact"], f["address"])
    else:
        user.update_profile(f["first_name"], f["last_name"], f["contact"])


def _save_email(user):
    email = request.form.get("email", "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 150:
        raise ValueError("Enter a valid email address.")
    if not user.check_password(request.form.get("current_password", "")):
        raise ValueError("Your current password is not correct.")
    if email != user.email and query("SELECT id FROM users WHERE email=%s", (email,), one=True):
        raise ValueError("That email is already used by another account.")
    user.set_email(email)


def _save_password(user):
    if not user.check_password(request.form.get("current_password", "")):
        raise ValueError("Your current password is not correct.")
    problem = _valid_password(request.form.get("password", ""), request.form.get("confirm", ""))
    if problem:
        raise ValueError(problem)
    user.set_password(request.form.get("password", ""))
