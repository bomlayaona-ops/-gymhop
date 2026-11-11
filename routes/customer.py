"""Customer side: cart, checkout, membership, trainer booking, my activity, notifications."""
from collections import defaultdict
from datetime import date, datetime, time as dtime
from decimal import Decimal
import pymysql
from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, g, current_app)
from db import query, commit, rollback
from models import (Gym, Product, Cart, MembershipPlan, Membership, Trainer, Booking, Order, Payment, Notification)
from models.payment import METHODS, PaymentMethod
from utils.security import login_required
from utils.uploads import save_image

customer = Blueprint("customer", __name__)


def read_payment_form(allowed):
    """Reads method / reference number / optional proof screenshot. `allowed` = the methods this gym (or gyms)
    accepts. Raises ValueError if invalid."""
    method = request.form.get("method", "")
    if method not in allowed:
        raise ValueError("Please choose a payment method.")
    ref = request.form.get("reference", "").strip()[:80]
    if method != "cash_onsite" and len(ref) < 6:
        raise ValueError(f"Enter the {METHODS[method]} reference number from your receipt.")
    proof = save_image(request.files.get("proof"), "proofs")
    return method, (ref or None), proof


def open_gym_or_404(gym_id):
    gym = Gym.get(gym_id)
    if not gym or gym["approval_status"] != "approved":
        abort(404)
    return gym


# ------------------------------------------------------------------ cart
@customer.route("/dashboard")
@login_required("customer")
def dashboard():
    return render_template("customer/dashboard.html", s=g.user.summary())


@customer.route("/cart")
@login_required("customer")
def cart():
    items = Cart.items(g.user.id)
    total = sum(Decimal(str(i["line_total"])) for i in items)
    return render_template("customer/cart.html", items=items, total=total)


@customer.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required("customer")
def cart_add(product_id):
    p = query("SELECT p.*, g.is_open, g.approval_status FROM products p JOIN gyms g ON g.id=p.gym_id WHERE p.id=%s",
              (product_id,), one=True)
    if not p or not p["is_active"] or p["approval_status"] != "approved":
        abort(404)
    try:
        qty = max(1, min(int(request.form.get("quantity", "1")), 99))
    except ValueError:
        qty = 1
    if not p["is_open"]:
        flash("This gym is currently closed for orders.", "warning")
    elif p["stock"] < 1:
        flash("Sorry, this item is out of stock.", "danger")
    else:
        have = next((i["quantity"] for i in Cart.items(g.user.id) if i["product_id"] == product_id), 0)
        if have + qty > p["stock"]:
            flash(f"Only {p['stock']} in stock.", "warning")
        else:
            Cart.add(g.user.id, product_id, qty)
            commit()
            flash("Added to your cart.", "success")
    return redirect(request.referrer or url_for("main.shop"))


@customer.route("/cart/update/<int:product_id>", methods=["POST"])
@login_required("customer")
def cart_update(product_id):
    try:
        qty = int(request.form.get("quantity", "1"))
    except ValueError:
        qty = 1
    p = query("SELECT stock FROM products WHERE id=%s", (product_id,), one=True)
    if p:
        Cart.set_qty(g.user.id, product_id, min(qty, p["stock"]))
        commit()
    return redirect(url_for("customer.cart"))


@customer.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required("customer")
def cart_remove(product_id):
    Cart.set_qty(g.user.id, product_id, 0)
    commit()
    return redirect(url_for("customer.cart"))


@customer.route("/checkout", methods=["GET", "POST"])
@login_required("customer")
def checkout():
    items = Cart.items(g.user.id)
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("main.shop"))
    by_gym = defaultdict(list)
    for i in items:
        by_gym[i["gym_id"]].append(i)
    totals = {gid: sum(Decimal(str(i["line_total"])) for i in rows) for gid, rows in by_gym.items()}
    grand = sum(totals.values())
    default_address = g.user.profile.get("address", "")
    gym_names = {gid: rows[0]["gym_name"] for gid, rows in by_gym.items()}
    methods, panels = PaymentMethod.options_for(gym_names, totals)

    if request.method == "POST":
        try:
            method, ref, proof = read_payment_form(methods)
            address = request.form.get("address", "").strip()[:255]
            if not address:
                raise ValueError("Please enter your delivery / pick-up address.")
            created = []
            for gid, rows in by_gym.items():
                gym = Gym.get(gid)
                if not gym or gym["approval_status"] != "approved" or not gym["is_open"]:
                    raise ValueError(f"{rows[0]['gym_name']} is not accepting orders right now.")
                for r in rows:   # lock + re-check stock
                    live = query("SELECT stock, is_active FROM products WHERE id=%s FOR UPDATE", (r["product_id"],), one=True)
                    if not live or not live["is_active"] or live["stock"] < r["quantity"]:
                        raise ValueError(f"Not enough stock for {r['name']}. Please update your cart.")
                order_id, total = Order.create_for_gym(g.user.id, gid, rows, address)
                Payment.create(g.user.id, gid, total, method, ref, proof, order_id=order_id)
                Notification.notify_gym_admins(gid, "New order", f"A customer placed an order worth ₱{total:.2f}.", "/admin/orders")
                created.append(order_id)
            Cart.clear(g.user.id)
            commit()
            flash("Order placed! The gym will confirm your payment shortly.", "success")
            return redirect(url_for("customer.my_activity"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
        except Exception:
            rollback()
            current_app.logger.exception("Checkout failed")
            flash("Something went wrong placing your order.", "danger")
    return render_template("customer/checkout.html", by_gym=by_gym, totals=totals, grand=grand,
                           address=default_address, methods=methods, panels=panels, gym_count=len(by_gym))


# ------------------------------------------------------------------ memberships
@customer.route("/gym/<int:gym_id>/join/<int:plan_id>", methods=["GET", "POST"])
@login_required("customer")
def join(gym_id, plan_id):
    gym = open_gym_or_404(gym_id)
    plan = MembershipPlan.get_for_gym(gym_id, plan_id)
    if not plan or not plan["is_active"]:
        abort(404)
    if not gym["is_open"]:
        flash("This gym is not accepting new members right now.", "warning")
        return redirect(url_for("main.gym_detail", slug=gym["slug"]))
    if Membership.has_open_application(g.user.id, gym_id):
        flash("You already have a pending or active membership at this gym.", "warning")
        return redirect(url_for("customer.my_activity"))
    methods, panels = PaymentMethod.options_for({gym_id: gym["name"]}, {gym_id: plan["price"]})
    if request.method == "POST":
        try:
            method, ref, proof = read_payment_form(methods)
            mid = Membership.apply(g.user.id, gym_id, plan_id)
            Payment.create(g.user.id, gym_id, plan["price"], method, ref, proof, membership_id=mid)
            Notification.notify_gym_admins(gym_id, "New membership application",
                                           f"{g.user.full_name} applied for {plan['name']}.", "/admin/memberships")
            commit()
            flash("Application sent! Your membership activates once the gym confirms your payment.", "success")
            return redirect(url_for("customer.my_activity"))
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
    return render_template("customer/pay.html", gym=gym, title=f"Join {gym['name']}",
                           summary=f"{plan['name']} · {plan['duration_days']} days", amount=plan["price"],
                           methods=methods, panels=panels, cancel_url=url_for("main.gym_detail", slug=gym["slug"]))


# ------------------------------------------------------------------ trainer booking
@customer.route("/trainer/<int:trainer_id>/book", methods=["GET", "POST"])
@login_required("customer")
def book_trainer(trainer_id):
    trainer = Trainer.get(trainer_id)
    if not trainer or not trainer["is_available"]:
        abort(404)
    gym = open_gym_or_404(trainer["gym_id"])
    if not gym["is_open"]:
        flash("This gym is not taking bookings right now.", "warning")
        return redirect(url_for("main.gym_detail", slug=gym["slug"]))
    methods, panels = PaymentMethod.options_for({gym["id"]: gym["name"]}, {gym["id"]: trainer["rate_per_session"]})
    if request.method == "POST":
        try:
            try:
                d = datetime.strptime(request.form.get("session_date", ""), "%Y-%m-%d").date()
                t = datetime.strptime(request.form.get("session_time", ""), "%H:%M").time()
            except ValueError:
                raise ValueError("Choose a valid date and time.")
            if datetime.combine(d, t) <= datetime.now():
                raise ValueError("Choose a future date and time.")
            if Booking.slot_taken(trainer_id, d, t):
                raise ValueError("That time slot is already booked. Pick another.")
            method, ref, proof = read_payment_form(methods)
            bid = Booking.create(g.user.id, trainer, d, t, request.form.get("notes", "").strip()[:255])
            Payment.create(g.user.id, gym["id"], trainer["rate_per_session"], method, ref, proof, booking_id=bid)
            Notification.notify_gym_admins(gym["id"], "New trainer booking",
                                           f"{g.user.full_name} booked {trainer['full_name']} on {d}.", "/admin/bookings")
            commit()
            flash("Booking sent! It is confirmed once the gym verifies your payment.", "success")
            return redirect(url_for("customer.my_activity"))
        except pymysql.err.IntegrityError:
            rollback()
            flash("That time slot was just taken. Pick another.", "danger")
        except ValueError as exc:
            rollback()
            flash(str(exc), "danger")
    return render_template("customer/book_trainer.html", gym=gym, trainer=trainer, methods=methods, panels=panels,
                           today=date.today().isoformat())


# ------------------------------------------------------------------ my activity
@customer.route("/my-activity")
@login_required("customer")
def my_activity():
    Membership.expire_old()
    commit()
    return render_template("customer/my_activity.html",
                           memberships=Membership.for_customer(g.user.id),
                           orders=Order.for_customer(g.user.id),
                           bookings=Booking.for_customer(g.user.id),
                           payments=Payment.for_customer(g.user.id))


@customer.route("/my-activity/cancel-order/<int:order_id>", methods=["POST"])
@login_required("customer")
def cancel_order(order_id):
    o = query("SELECT o.*, (SELECT status FROM payments p WHERE p.order_id=o.id LIMIT 1) AS pay FROM product_orders o"
              " WHERE o.id=%s AND o.customer_id=%s", (order_id, g.user.id), one=True)
    if not o:
        abort(404)
    if o["status"] == "pending" and o["pay"] == "pending":
        Order.set_status(order_id, "cancelled")
        Order.restore_stock(order_id)
        from db import execute
        execute("UPDATE payments SET status='cancelled' WHERE order_id=%s", (order_id,))
        commit()
        flash("Order cancelled.", "success")
    else:
        flash("This order can no longer be cancelled. Contact the gym.", "warning")
    return redirect(url_for("customer.my_activity"))


@customer.route("/notifications")
@login_required("customer", "admin")
def notifications():
    items = Notification.recent(g.user.id)
    Notification.mark_all_read(g.user.id)
    commit()
    return render_template("notifications.html", items=items)


@customer.route("/favorites")
@login_required("customer")
def favorites():
    gyms = query("SELECT g.* FROM gyms g JOIN favorites f ON f.gym_id=g.id WHERE f.customer_id=%s"
                 " AND g.approval_status='approved'", (g.user.id,))
    return render_template("customer/favorites.html", gyms=gyms)
