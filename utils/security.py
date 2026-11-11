"""Login helpers and role protection."""
from functools import wraps
from flask import session, redirect, url_for, flash, abort, g
from models import User


def load_current_user():
    uid = session.get("user_id")
    g.user = User.find_by_id(uid) if uid else None
    if g.user and not g.user.is_active:
        session.clear()
        g.user = None


def home_for(user):
    """Where a logged-in person lands: gym owners -> gym dashboard, customers -> their dashboard."""
    return url_for("admin.dashboard") if user.role == "admin" else url_for("customer.dashboard")


def login_required(*roles):
    """@login_required('customer')  or  @login_required('admin')
    Anyone who is not logged in is sent to the matching login page first."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("user")
            if not user:
                flash("Please log in first.", "warning")
                return redirect(url_for("admin_auth.admin_login" if roles == ("admin",) else "auth.login"))
            if roles and user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def gym_admin(fn):
    """Admin pages: loads the admin's own gym into g.gym (an admin can only ever see this gym)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from models import Gym
        gym = Gym.get(g.user.gym_id) if g.user.gym_id else None
        if not gym:
            abort(403)
        g.gym = gym
        return fn(*args, **kwargs)
    return wrapper


approved_admin = gym_admin   # old name still works
