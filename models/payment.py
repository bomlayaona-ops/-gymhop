"""Payments (manual GCash / Maya / cash on-site) and the sales ledger."""
import secrets
from datetime import datetime
from db import query, execute
from models.order import Order
from models.membership import Membership, MembershipPlan
from models.trainer import Booking
from models.notification import Notification

# Online methods each gym sets up with its own QR code. Cash on-site is always available.
ONLINE_METHODS = {"gcash": "GCash", "maya": "Maya", "paymongo": "PayMongo", "maribank": "MariBank"}
METHODS = {**ONLINE_METHODS, "cash_onsite": "Cash on-site"}


class PaymentMethod:
    """A gym's own payment account for one provider: QR code, account name/number and a description."""

    @staticmethod
    def for_gym(gym_id):
        """{method: row} for every provider this gym has saved (enabled or not)."""
        rows = query("SELECT * FROM gym_payment_methods WHERE gym_id=%s", (gym_id,))
        return {r["method"]: r for r in rows}

    @staticmethod
    def enabled_for_gym(gym_id):
        return {m: r for m, r in PaymentMethod.for_gym(gym_id).items() if r["is_enabled"]}

    @staticmethod
    def save(gym_id, method, account_name, account_number, description, qr_image, is_enabled):
        execute(
            "INSERT INTO gym_payment_methods (gym_id, method, account_name, account_number, description, qr_image, is_enabled)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE account_name=VALUES(account_name),"
            " account_number=VALUES(account_number), description=VALUES(description), qr_image=VALUES(qr_image),"
            " is_enabled=VALUES(is_enabled)",
            (gym_id, method, account_name, account_number, description, qr_image, 1 if is_enabled else 0))

    @staticmethod
    def options_for(gyms, amounts=None):
        """What a customer sees when paying `gyms` ({gym_id: gym name}).
        Returns (methods, panels): methods every one of these gyms accepts (+ cash on-site), and for each method
        the QR / account / description panel of every gym. `amounts` = {gym_id: amount to send}."""
        per_gym = {gid: PaymentMethod.enabled_for_gym(gid) for gid in gyms}
        common = [m for m in ONLINE_METHODS if all(m in per_gym[gid] for gid in gyms)]
        methods = {m: ONLINE_METHODS[m] for m in common}
        methods["cash_onsite"] = METHODS["cash_onsite"]
        panels = {m: [dict(per_gym[gid][m], gym_name=name, amount=(amounts or {}).get(gid)) for gid, name in gyms.items()]
                  for m in common}
        return methods, panels


class Payment:
    @staticmethod
    def create(customer_id, gym_id, amount, method, external_reference=None, proof_image=None,
               order_id=None, membership_id=None, booking_id=None):
        """A payment belongs to exactly ONE of: order, membership, booking."""
        return execute(
            "INSERT INTO payments (reference_no, customer_id, gym_id, order_id, membership_id, booking_id,"
            " amount, method, external_reference, proof_image) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (f"GHP-{datetime.utcnow():%y%m%d}-{secrets.token_hex(4).upper()}", customer_id, gym_id,
             order_id, membership_id, booking_id, amount, method, external_reference, proof_image))

    @staticmethod
    def get_for_gym(gym_id, payment_id):
        return query("SELECT * FROM payments WHERE id=%s AND gym_id=%s", (payment_id, gym_id), one=True)

    @staticmethod
    def for_gym(gym_id):
        return query(
            "SELECT p.*, c.first_name, c.last_name, u.email,"
            " CASE WHEN p.order_id IS NOT NULL THEN 'Product order' WHEN p.membership_id IS NOT NULL THEN 'Membership'"
            " ELSE 'Trainer session' END AS target"
            " FROM payments p JOIN users u ON u.id=p.customer_id LEFT JOIN customer_profiles c ON c.user_id=p.customer_id"
            " WHERE p.gym_id=%s ORDER BY p.created_at DESC", (gym_id,))

    @staticmethod
    def for_customer(customer_id):
        return query(
            "SELECT p.*, g.name AS gym_name,"
            " CASE WHEN p.order_id IS NOT NULL THEN 'Product order' WHEN p.membership_id IS NOT NULL THEN 'Membership'"
            " ELSE 'Trainer session' END AS target FROM payments p JOIN gyms g ON g.id=p.gym_id"
            " WHERE p.customer_id=%s ORDER BY p.created_at DESC", (customer_id,))

    @staticmethod
    def _category(p):
        if p["order_id"]:
            return "product"
        return "membership" if p["membership_id"] else "training"

    @staticmethod
    def verify(payment, admin_user_id):
        """Admin confirms the money arrived. Activates the membership / order / booking."""
        if payment["status"] != "pending":
            return False
        execute("UPDATE payments SET status='paid', verified_by=%s, verified_at=%s WHERE id=%s",
                (admin_user_id, datetime.utcnow(), payment["id"]))
        execute("INSERT INTO transactions (payment_id, gym_id, type, amount, category) VALUES (%s,%s,'sale',%s,%s)",
                (payment["id"], payment["gym_id"], payment["amount"], Payment._category(payment)))
        if payment["order_id"]:
            Order.set_status(payment["order_id"], "processing")
            msg = "Your order payment was confirmed."
        elif payment["membership_id"]:
            m = query("SELECT plan_id FROM memberships WHERE id=%s", (payment["membership_id"],), one=True)
            Membership.activate(payment["membership_id"], MembershipPlan.get(m["plan_id"])["duration_days"])
            msg = "Your membership is now active. Welcome!"
        else:
            Booking.set_status(payment["booking_id"], "confirmed")
            msg = "Your trainer session is confirmed."
        Notification.send(payment["customer_id"], "Payment confirmed", msg, "/my-activity")
        return True

    @staticmethod
    def reject(payment):
        """Payment not received. Cancels what it was paying for."""
        if payment["status"] != "pending":
            return False
        execute("UPDATE payments SET status='failed' WHERE id=%s", (payment["id"],))
        if payment["order_id"]:
            Order.set_status(payment["order_id"], "cancelled")
            Order.restore_stock(payment["order_id"])
        elif payment["membership_id"]:
            Membership.set_status(payment["membership_id"], "rejected")
        else:
            Booking.set_status(payment["booking_id"], "cancelled")
        Notification.send(payment["customer_id"], "Payment not confirmed",
                          "The gym could not confirm your payment. Please contact the gym.", "/my-activity")
        return True

    # ---- reports ----
    @staticmethod
    def ledger(gym_id, since=None):
        sql = "SELECT * FROM transactions WHERE gym_id=%s"
        args = [gym_id]
        if since:
            sql += " AND created_at>=%s"
            args.append(since)
        return query(sql + " ORDER BY created_at", args)
