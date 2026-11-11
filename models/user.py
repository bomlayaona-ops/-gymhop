"""User classes. Customer and Admin both inherit from User (shared login/password/photo behaviour)."""
from werkzeug.security import generate_password_hash, check_password_hash
from db import query, execute


class User:
    role = "user"

    def __init__(self, row):
        self.id = row["id"]
        self.email = row["email"]
        self.password_hash = row["password_hash"]
        self.role = row["role"]
        self.is_verified = bool(row["is_verified"])
        self.is_active = bool(row["is_active"])
        self.photo = row.get("profile_photo")
        self.first_name = ""
        self.last_name = ""

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email.split("@")[0]

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def load_profile(self):
        pass

    # ---- account changes (encapsulated here so routes stay short) ----
    def set_password(self, new_password):
        self.password_hash = generate_password_hash(new_password)
        execute("UPDATE users SET password_hash=%s WHERE id=%s", (self.password_hash, self.id))

    def set_email(self, new_email):
        self.email = new_email.lower()
        execute("UPDATE users SET email=%s WHERE id=%s", (self.email, self.id))

    def set_photo(self, path):
        self.photo = path
        execute("UPDATE users SET profile_photo=%s WHERE id=%s", (path, self.id))

    # ---- factory helpers ----
    @staticmethod
    def _build(row):
        if not row:
            return None
        cls = {"customer": Customer, "admin": Admin}.get(row["role"], User)
        user = cls(row)
        user.load_profile()
        return user

    @staticmethod
    def find_by_id(user_id):
        return User._build(query("SELECT * FROM users WHERE id=%s", (user_id,), one=True))

    @staticmethod
    def find_by_email(email):
        return User._build(query("SELECT * FROM users WHERE email=%s", (email.lower(),), one=True))

    @staticmethod
    def create(email, password, role):
        return execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s,%s,%s)",
            (email.lower(), generate_password_hash(password), role),
        )

    @staticmethod
    def mark_verified(user_id):
        execute("UPDATE users SET is_verified=1 WHERE id=%s", (user_id,))


class Customer(User):
    def load_profile(self):
        p = query("SELECT * FROM customer_profiles WHERE user_id=%s", (self.id,), one=True)
        self.profile = p or {}
        if p:
            self.first_name, self.last_name = p["first_name"], p["last_name"]

    @staticmethod
    def create_profile(user_id, first, middle, last, dob, contact, address):
        execute(
            "INSERT INTO customer_profiles (user_id, first_name, middle_name, last_name,"
            " date_of_birth, contact_number, address) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (user_id, first, middle or None, last, dob, contact, address),
        )


    def update_profile(self, first, middle, last, dob, contact, address):
        execute("UPDATE customer_profiles SET first_name=%s, middle_name=%s, last_name=%s, date_of_birth=%s,"
                " contact_number=%s, address=%s WHERE user_id=%s",
                (first, middle or None, last, dob, contact, address, self.id))

    def summary(self):
        """Numbers and recent items for the customer dashboard."""
        one = lambda sql: query(sql, (self.id,), one=True)["n"]
        return {
            "active_memberships": one("SELECT COUNT(*) AS n FROM memberships WHERE customer_id=%s AND status='active'"),
            "open_orders": one("SELECT COUNT(*) AS n FROM product_orders WHERE customer_id=%s AND status IN ('pending','processing','ready')"),
            "upcoming_sessions": one("SELECT COUNT(*) AS n FROM trainer_bookings WHERE customer_id=%s AND status IN ('pending','confirmed') AND session_date>=CURDATE()"),
            "favorites": one("SELECT COUNT(*) AS n FROM favorites WHERE customer_id=%s"),
            "memberships": query("SELECT m.*, p.name AS plan_name, g.name AS gym_name, g.slug AS gym_slug FROM memberships m"
                                 " JOIN membership_plans p ON p.id=m.plan_id JOIN gyms g ON g.id=m.gym_id"
                                 " WHERE m.customer_id=%s ORDER BY m.applied_at DESC LIMIT 4", (self.id,)),
            "orders": query("SELECT o.*, g.name AS gym_name FROM product_orders o JOIN gyms g ON g.id=o.gym_id"
                            " WHERE o.customer_id=%s ORDER BY o.created_at DESC LIMIT 4", (self.id,)),
            "bookings": query("SELECT b.*, t.full_name AS trainer_name, g.name AS gym_name FROM trainer_bookings b"
                              " JOIN trainers t ON t.id=b.trainer_id JOIN gyms g ON g.id=b.gym_id"
                              " WHERE b.customer_id=%s ORDER BY b.session_date DESC LIMIT 4", (self.id,)),
        }


class Admin(User):
    gym_id = None

    def load_profile(self):
        p = query("SELECT * FROM admin_profiles WHERE user_id=%s", (self.id,), one=True)
        self.profile = p or {}
        if p:
            self.first_name, self.last_name = p["first_name"], p["last_name"]
            self.gym_id = p["gym_id"]

    def update_profile(self, first, last, contact):
        execute("UPDATE admin_profiles SET first_name=%s, last_name=%s, contact_number=%s WHERE user_id=%s",
                (first, last, contact, self.id))

    @staticmethod
    def create_profile(user_id, gym_id, first, last, contact):
        execute(
            "INSERT INTO admin_profiles (user_id, gym_id, first_name, last_name, contact_number)"
            " VALUES (%s,%s,%s,%s,%s)",
            (user_id, gym_id, first, last, contact),
        )

