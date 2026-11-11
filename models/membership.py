"""Membership plans and customer memberships."""
from datetime import date, timedelta
from db import query, execute


class MembershipPlan:
    @staticmethod
    def list_for_gym(gym_id, only_active=False):
        sql = "SELECT * FROM membership_plans WHERE gym_id=%s"
        if only_active:
            sql += " AND is_active=1"
        return query(sql + " ORDER BY price", (gym_id,))

    @staticmethod
    def get(plan_id):
        return query("SELECT * FROM membership_plans WHERE id=%s", (plan_id,), one=True)

    @staticmethod
    def get_for_gym(gym_id, plan_id):
        return query("SELECT * FROM membership_plans WHERE id=%s AND gym_id=%s", (plan_id, gym_id), one=True)

    @staticmethod
    def create(gym_id, name, description, price, duration_days):
        return execute("INSERT INTO membership_plans (gym_id, name, description, price, duration_days) VALUES (%s,%s,%s,%s,%s)",
                       (gym_id, name, description, price, duration_days))

    @staticmethod
    def update(gym_id, plan_id, name, description, price, duration_days):
        execute("UPDATE membership_plans SET name=%s, description=%s, price=%s, duration_days=%s WHERE id=%s AND gym_id=%s",
                (name, description, price, duration_days, plan_id, gym_id))

    @staticmethod
    def delete(gym_id, plan_id):
        """True if deleted; False if members already use this plan (then it is only hidden)."""
        if query("SELECT id FROM memberships WHERE plan_id=%s LIMIT 1", (plan_id,), one=True):
            execute("UPDATE membership_plans SET is_active=0 WHERE id=%s AND gym_id=%s", (plan_id, gym_id))
            return False
        execute("DELETE FROM membership_plans WHERE id=%s AND gym_id=%s", (plan_id, gym_id))
        return True

    @staticmethod
    def toggle_active(gym_id, plan_id):
        execute("UPDATE membership_plans SET is_active=1-is_active WHERE id=%s AND gym_id=%s", (plan_id, gym_id))


class Membership:
    @staticmethod
    def apply(customer_id, gym_id, plan_id):
        return execute("INSERT INTO memberships (customer_id, gym_id, plan_id, status) VALUES (%s,%s,%s,'pending')",
                       (customer_id, gym_id, plan_id))

    @staticmethod
    def has_open_application(customer_id, gym_id):
        """True if the customer already has a pending or active membership at this gym."""
        return bool(query("SELECT id FROM memberships WHERE customer_id=%s AND gym_id=%s"
                          " AND (status='pending' OR (status='active' AND end_date>=%s))",
                          (customer_id, gym_id, date.today()), one=True))

    @staticmethod
    def get_for_gym(gym_id, membership_id):
        return query("SELECT m.*, p.duration_days, p.name AS plan_name FROM memberships m"
                     " JOIN membership_plans p ON p.id=m.plan_id WHERE m.id=%s AND m.gym_id=%s",
                     (membership_id, gym_id), one=True)

    @staticmethod
    def activate(membership_id, duration_days):
        start = date.today()
        execute("UPDATE memberships SET status='active', start_date=%s, end_date=%s WHERE id=%s",
                (start, start + timedelta(days=duration_days), membership_id))

    @staticmethod
    def set_status(membership_id, status):
        execute("UPDATE memberships SET status=%s WHERE id=%s", (status, membership_id))

    @staticmethod
    def expire_old():
        execute("UPDATE memberships SET status='expired' WHERE status='active' AND end_date<%s", (date.today(),))

    @staticmethod
    def for_customer(customer_id):
        return query(
            "SELECT m.*, p.name AS plan_name, p.price, g.name AS gym_name, g.slug AS gym_slug FROM memberships m"
            " JOIN membership_plans p ON p.id=m.plan_id JOIN gyms g ON g.id=m.gym_id"
            " WHERE m.customer_id=%s ORDER BY m.applied_at DESC", (customer_id,))

    @staticmethod
    def for_gym(gym_id):
        return query(
            "SELECT m.*, p.name AS plan_name, p.price, c.first_name, c.last_name, c.contact_number, u.email,"
            " (SELECT status FROM payments pay WHERE pay.membership_id=m.id LIMIT 1) AS payment_status"
            " FROM memberships m JOIN membership_plans p ON p.id=m.plan_id"
            " JOIN users u ON u.id=m.customer_id LEFT JOIN customer_profiles c ON c.user_id=m.customer_id"
            " WHERE m.gym_id=%s ORDER BY m.applied_at DESC", (gym_id,))
