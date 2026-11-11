"""Gym admin side. Every query is limited to the admin's OWN gym (g.user.gym_id)."""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g, jsonify
from db import query, execute, commit, rollback
from models.payment import PaymentMethod, ONLINE_METHODS
from models import (Gym, Product, MembershipPlan, Membership, Trainer, Booking, Order, Payment, Notification)
from models.product import CATEGORIES
from utils.security import login_required, approved_admin
from utils.uploads import save_image
from utils.ph_address import read_address

admin = Blueprint("admin", __name__, url_prefix="/admin")


def _money(value, label="Price"):
    try:
        v = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError(f"{label} must be a number.")
    if v <= 0 or v > Decimal("9999999"):
        raise ValueError(f"{label} must be greater than zero.")
    return v


def _int(value, label, minimum=0, maximum=100000):
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if not minimum <= v <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return v


# ------------------------------------------------------------------ dashboard
@admin.route("/")
@login_required("admin")
@approved_admin
def dashboard():
    gid = g.gym["id"]
    since = datetime.utcnow() - timedelta(days=29)
    ledger = Payment.ledger(gid, since)
    per_day = defaultdict(float)
    for t in ledger:
        per_day[t["created_at"].strftime("%b %d")] += float(t["amount"]) * (1 if t["type"] == "sale" else -1)
    labels = [(since + timedelta(days=i)).strftime("%b %d") for i in range(30)]
    totals = {}
    for row in query("SELECT category, SUM(amount) AS s FROM transactions WHERE gym_id=%s AND type='sale' GROUP BY category", (gid,)):
        totals[row["category"]] = float(row["s"])
    stats = {
        "revenue": sum(totals.values()),
        "members": query("SELECT COUNT(*) AS n FROM memberships WHERE gym_id=%s AND status='active'", (gid,), one=True)["n"],
        "pending_payments": query("SELECT COUNT(*) AS n FROM payments WHERE gym_id=%s AND status='pending'", (gid,), one=True)["n"],
        "orders": query("SELECT COUNT(*) AS n FROM product_orders WHERE gym_id=%s", (gid,), one=True)["n"],
        "low_stock": query("SELECT COUNT(*) AS n FROM products WHERE gym_id=%s AND is_active=1 AND stock<=5", (gid,), one=True)["n"],
    }
    recent = Payment.for_gym(gid)[:6]
    return render_template("admin/dashboard.html", gym=g.gym, stats=stats, recent=recent,
                           chart_labels=labels, chart_values=[round(per_day.get(l, 0), 2) for l in labels],
                           split_labels=["Products", "Memberships", "Training"],
                           split_values=[totals.get("product", 0), totals.get("membership", 0), totals.get("training", 0)])


# ------------------------------------------------------------------ gym profile
@admin.route("/gym", methods=["GET", "POST"])
@login_required("admin")
@approved_admin
def gym_profile():
    gym = g.gym
    if request.method == "POST":
        try:
            data = {k: request.form.get(k, "").strip() for k in
                    ("name", "description", "contact_number", "email", "operating_hours",
                     "facilities", "equipment", "rules", "facebook_url", "instagram_url")}
            addr, addr_error = read_address(request.form)
            if addr_error:
                raise ValueError(addr_error)
            data.update(address=addr["detail"], city=addr["city"], province=addr["province"])
            if not data["name"]:
                raise ValueError("Gym name is required.")
            data["contact_number"] = re.sub(r"[\s-]", "", data["contact_number"])
            if data["contact_number"] and not re.match(r"^09\d{9}$", data["contact_number"]):
                raise ValueError("Contact number must be 11 digits starting with 09 (example 09171234567).")
            for k in ("facebook_url", "instagram_url"):
                if data[k] and not data[k].startswith(("http://", "https://")):
                    raise ValueError("Social links must start with https://")
            Gym.update_profile(gym["id"], data)
            logo = save_image(request.files.get("logo"), "gyms")
            cover = save_image(request.files.get("cover"), "gyms")
            if logo:
                Gym.set_image(gym["id"], "logo", logo)
            if cover:
                Gym.set_image(gym["id"], "cover_photo", cover)
            lat, lng = request.form.get("latitude", "").strip(), request.form.get("longitude", "").strip()
            if lat and lng:
                try:
                    lat_f, lng_f = float(lat), float(lng)
                except ValueError:
                    raise ValueError("Map coordinates must be numbers, e.g. 14.5995 and 120.9842.")
                if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
                    raise ValueError("Map coordinates are out of range.")
                Gym.set_location(gym["id"], lat_f, lng_f)
            Gym.set_open(gym["id"], request.form.get("is_open") == "1")
            commit()
            flash("Gym profile saved.", "success")
            return redirect(url_for("admin.gym_profile"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
        gym = Gym.get(gym["id"])
    return render_template("admin/gym_profile.html", gym=gym, location=Gym.location(gym["id"]))


# ------------------------------------------------------------------ products
@admin.route("/products", methods=["GET", "POST"])
@login_required("admin")
@approved_admin
def products():
    gid = g.gym["id"]
    edit = None
    if request.args.get("edit"):
        edit = Product.get_for_gym(gid, int(request.args["edit"])) if request.args["edit"].isdigit() else None
    if request.method == "POST":
        pid = request.form.get("product_id", "")
        try:
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "")
            if not name or category not in CATEGORIES:
                raise ValueError("Enter a product name and choose a category.")
            price = _money(request.form.get("price"))
            stock = _int(request.form.get("stock"), "Stock")
            description = request.form.get("description", "").strip()
            image = save_image(request.files.get("image"), "products")   # OPTIONAL: default picture if empty
            if pid.isdigit():
                if not Product.get_for_gym(gid, int(pid)):
                    abort(404)
                Product.update(gid, int(pid), category, name, description, price, stock, image)
                flash("Product updated.", "success")
            else:
                Product.create(gid, category, name, description, price, stock, image)
                flash("Product added.", "success")
            commit()
            return redirect(url_for("admin.products"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
    return render_template("admin/products.html", products=Product.list_for_gym(gid), edit=edit, categories=CATEGORIES)


@admin.route("/products/<int:product_id>/toggle", methods=["POST"])
@login_required("admin")
@approved_admin
def product_toggle(product_id):
    Product.toggle_active(g.gym["id"], product_id)
    commit()
    return redirect(url_for("admin.products"))


@admin.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required("admin")
@approved_admin
def product_delete(product_id):
    if not Product.get_for_gym(g.gym["id"], product_id):
        abort(404)
    if Product.delete(g.gym["id"], product_id):
        flash("Product deleted.", "success")
    else:
        flash("Product is already used in past records, so it was hidden instead of deleted.", "success")
    commit()
    return redirect(url_for("admin.products"))


@admin.route("/products/<int:product_id>/remove-image", methods=["POST"])
@login_required("admin")
@approved_admin
def product_remove_image(product_id):
    execute("UPDATE products SET image=NULL WHERE id=%s AND gym_id=%s", (product_id, g.gym["id"]))
    commit()
    flash("Photo removed. The default picture will be shown.", "success")
    return redirect(url_for("admin.products", edit=product_id))


# ------------------------------------------------------------------ plans
@admin.route("/plans", methods=["GET", "POST"])
@login_required("admin")
@approved_admin
def plans():
    gid = g.gym["id"]
    edit = None
    if request.args.get("edit", "").isdigit():
        edit = MembershipPlan.get_for_gym(gid, int(request.args["edit"]))
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            if not name:
                raise ValueError("Plan name is required.")
            price = _money(request.form.get("price"))
            days = _int(request.form.get("duration_days"), "Duration (days)", 1, 3650)
            desc = request.form.get("description", "").strip()
            pid = request.form.get("plan_id", "")
            if pid.isdigit() and MembershipPlan.get_for_gym(gid, int(pid)):
                MembershipPlan.update(gid, int(pid), name, desc, price, days)
                flash("Plan updated.", "success")
            else:
                MembershipPlan.create(gid, name, desc, price, days)
                flash("Plan added.", "success")
            commit()
            return redirect(url_for("admin.plans"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
    return render_template("admin/plans.html", plans=MembershipPlan.list_for_gym(gid), edit=edit)


@admin.route("/plans/<int:plan_id>/toggle", methods=["POST"])
@login_required("admin")
@approved_admin
def plan_toggle(plan_id):
    MembershipPlan.toggle_active(g.gym["id"], plan_id)
    commit()
    return redirect(url_for("admin.plans"))


@admin.route("/plans/<int:plan_id>/delete", methods=["POST"])
@login_required("admin")
@approved_admin
def plan_delete(plan_id):
    if not MembershipPlan.get_for_gym(g.gym["id"], plan_id):
        abort(404)
    if MembershipPlan.delete(g.gym["id"], plan_id):
        flash("Plan deleted.", "success")
    else:
        flash("Plan is already used in past records, so it was hidden instead of deleted.", "success")
    commit()
    return redirect(url_for("admin.plans"))


# ------------------------------------------------------------------ trainers
@admin.route("/trainers", methods=["GET", "POST"])
@login_required("admin")
@approved_admin
def trainers():
    gid = g.gym["id"]
    edit = None
    if request.args.get("edit", "").isdigit():
        edit = Trainer.get_for_gym(gid, int(request.args["edit"]))
    if request.method == "POST":
        try:
            name = request.form.get("full_name", "").strip()
            if not name:
                raise ValueError("Trainer name is required.")
            rate = _money(request.form.get("rate"), "Rate")
            years = _int(request.form.get("experience_years", "0"), "Experience", 0, 80)
            spec = request.form.get("specialization", "").strip()
            desc = request.form.get("description", "").strip()
            avail = request.form.get("availability", "").strip()
            image = save_image(request.files.get("image"), "trainers")
            tid = request.form.get("trainer_id", "")
            if tid.isdigit() and Trainer.get_for_gym(gid, int(tid)):
                Trainer.update(gid, int(tid), name, spec, years, desc, rate, avail, image)
                flash("Trainer updated.", "success")
            else:
                Trainer.create(gid, name, spec, years, desc, rate, avail, image)
                flash("Trainer added.", "success")
            commit()
            return redirect(url_for("admin.trainers"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
    return render_template("admin/trainers.html", trainers=Trainer.list_for_gym(gid), edit=edit)


@admin.route("/trainers/<int:trainer_id>/toggle", methods=["POST"])
@login_required("admin")
@approved_admin
def trainer_toggle(trainer_id):
    Trainer.toggle_available(g.gym["id"], trainer_id)
    commit()
    return redirect(url_for("admin.trainers"))


@admin.route("/trainers/<int:trainer_id>/delete", methods=["POST"])
@login_required("admin")
@approved_admin
def trainer_delete(trainer_id):
    if not Trainer.get_for_gym(g.gym["id"], trainer_id):
        abort(404)
    if Trainer.delete(g.gym["id"], trainer_id):
        flash("Trainer deleted.", "success")
    else:
        flash("Trainer is already used in past records, so it was hidden instead of deleted.", "success")
    commit()
    return redirect(url_for("admin.trainers"))


# ------------------------------------------------------------------ memberships / orders / bookings
@admin.route("/memberships")
@login_required("admin")
@approved_admin
def memberships():
    Membership.expire_old()
    commit()
    return render_template("admin/memberships.html", rows=Membership.for_gym(g.gym["id"]))


@admin.route("/orders")
@login_required("admin")
@approved_admin
def orders():
    return render_template("admin/orders.html", rows=Order.for_gym(g.gym["id"]))


@admin.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required("admin")
@approved_admin
def order_status(order_id):
    order = Order.get_for_gym(g.gym["id"], order_id)
    if not order:
        abort(404)
    status = request.form.get("status", "")
    if status not in ("processing", "ready", "completed", "cancelled"):
        abort(400)
    if order["status"] in ("completed", "cancelled"):
        flash("This order is already closed.", "warning")
    else:
        if status == "cancelled":
            Order.restore_stock(order_id)
        Order.set_status(order_id, status)
        Notification.send(order["customer_id"], "Order update", f"Your order {order['order_number']} is now {status}.", "/my-activity")
        commit()
        flash("Order updated.", "success")
    return redirect(url_for("admin.orders"))


@admin.route("/bookings")
@login_required("admin")
@approved_admin
def bookings():
    return render_template("admin/bookings.html", rows=Booking.for_gym(g.gym["id"]))


@admin.route("/bookings/<int:booking_id>/status", methods=["POST"])
@login_required("admin")
@approved_admin
def booking_status(booking_id):
    b = Booking.get_for_gym(g.gym["id"], booking_id)
    status = request.form.get("status", "")
    if not b or status not in ("completed", "cancelled"):
        abort(400)
    Booking.set_status(booking_id, status)
    Notification.send(b["customer_id"], "Trainer session update", f"Your session is now {status}.", "/my-activity")
    commit()
    flash("Booking updated.", "success")
    return redirect(url_for("admin.bookings"))


# ------------------------------------------------------------------ payments
@admin.route("/payments")
@login_required("admin")
@approved_admin
def payments():
    return render_template("admin/payments.html", rows=Payment.for_gym(g.gym["id"]),
                           accounts=PaymentMethod.for_gym(g.gym["id"]), providers=ONLINE_METHODS)


@admin.route("/payment-methods/<method>", methods=["POST"])
@login_required("admin")
@approved_admin
def payment_method_save(method):
    """Save one provider's QR code, account name/number and description."""
    if method not in ONLINE_METHODS:
        abort(404)
    label = ONLINE_METHODS[method]
    try:
        old = PaymentMethod.for_gym(g.gym["id"]).get(method)
        name = request.form.get("account_name", "").strip()[:120]
        number = re.sub(r"[^0-9+ \-]", "", request.form.get("account_number", "")).strip()[:40]
        description = request.form.get("description", "").strip()[:300]
        enabled = request.form.get("enabled") == "1"
        new_qr = save_image(request.files.get("qr"), "qr")
        if new_qr:
            qr = new_qr
        elif request.form.get("remove_qr") == "1":
            qr = None
        else:
            qr = old["qr_image"] if old else None
        if enabled and not (qr or number):
            raise ValueError(f"Add a {label} QR code or account number before turning it on.")
        PaymentMethod.save(g.gym["id"], method, name or None, number or None, description or None, qr, enabled)
        commit()
        flash(f"{label} saved. " + ("Customers can now pay with it." if enabled else "It is turned off, so customers will not see it."), "success")
    except ValueError as exc:
        rollback()
        flash(str(exc), "danger")
    return redirect(url_for("admin.payments") + "#payment-setup")


@admin.route("/payments/<int:payment_id>/<action>", methods=["POST"])
@login_required("admin")
@approved_admin
def payment_action(payment_id, action):
    p = Payment.get_for_gym(g.gym["id"], payment_id)
    if not p or action not in ("verify", "reject"):
        abort(404)
    done = Payment.verify(p, g.user.id) if action == "verify" else Payment.reject(p)
    commit()
    flash(("Payment confirmed." if action == "verify" else "Payment rejected.") if done else "Already handled.",
          "success" if done else "warning")
    return redirect(request.referrer or url_for("admin.payments"))


# ------------------------------------------------------------------ sales report
@admin.route("/sales")
@login_required("admin")
@approved_admin
def sales():
    rows = query("SELECT t.*, p.reference_no, p.method FROM transactions t JOIN payments p ON p.id=t.payment_id"
                 " WHERE t.gym_id=%s ORDER BY t.created_at DESC LIMIT 200", (g.gym["id"],))
    total = sum(float(r["amount"]) for r in rows if r["type"] == "sale")
    return render_template("admin/sales.html", rows=rows, total=total)
