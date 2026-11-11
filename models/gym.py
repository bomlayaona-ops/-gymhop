"""Gym storefronts."""
import re
import secrets
from db import query, execute


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or secrets.token_hex(3)


class Gym:
    @staticmethod
    def unique_slug(name):
        base = slugify(name)
        slug = base
        while query("SELECT id FROM gyms WHERE slug=%s", (slug,), one=True):
            slug = f"{base}-{secrets.token_hex(2)}"
        return slug

    @staticmethod
    def create(name, address, city, province, contact, email):
        return execute(
            "INSERT INTO gyms (name, slug, address, city, province, contact_number, email, approval_status)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'approved')",
            (name, Gym.unique_slug(name), address, city, province, contact, email),
        )

    @staticmethod
    def get(gym_id):
        return query("SELECT * FROM gyms WHERE id=%s", (gym_id,), one=True)

    @staticmethod
    def get_public(slug):
        return query("SELECT * FROM gyms WHERE slug=%s AND approval_status='approved'", (slug,), one=True)

    @staticmethod
    def search(q="", city="", only_open=False, province=""):
        sql = ("SELECT g.*, (SELECT ROUND(AVG(rating),1) FROM reviews r WHERE r.gym_id=g.id AND r.product_id IS NULL) AS avg_rating,"
               " (SELECT MIN(price) FROM membership_plans p WHERE p.gym_id=g.id AND p.is_active=1) AS from_price"
               " FROM gyms g WHERE g.approval_status='approved'")
        args = []
        if q:
            sql += " AND (g.name LIKE %s OR g.address LIKE %s OR g.city LIKE %s OR g.province LIKE %s OR g.description LIKE %s)"
            args += [f"%{q}%"] * 5
        if city:
            sql += " AND TRIM(g.city)=%s"
            args.append(city)
        if province:
            sql += " AND TRIM(g.province)=%s"
            args.append(province)
        if only_open:
            sql += " AND g.is_open=1"
        sql += " ORDER BY g.is_open DESC, g.name"
        return query(sql, args)

    @staticmethod
    def cities():
        rows = query("SELECT DISTINCT TRIM(city) AS city FROM gyms WHERE approval_status='approved' AND city IS NOT NULL AND TRIM(city)<>'' ORDER BY city")
        return [r["city"] for r in rows]

    @staticmethod
    def provinces():
        rows = query("SELECT DISTINCT TRIM(province) AS province FROM gyms WHERE approval_status='approved' AND province IS NOT NULL AND TRIM(province)<>'' ORDER BY province")
        return [r["province"] for r in rows]

    @staticmethod
    def update_profile(gym_id, data):
        execute(
            "UPDATE gyms SET name=%s, description=%s, address=%s, city=%s, province=%s, contact_number=%s,"
            " email=%s, operating_hours=%s, facilities=%s, equipment=%s, rules=%s, facebook_url=%s,"
            " instagram_url=%s WHERE id=%s",
            (data["name"], data["description"], data["address"], data["city"], data["province"],
             data["contact_number"], data["email"], data["operating_hours"], data["facilities"],
             data["equipment"], data["rules"], data["facebook_url"], data["instagram_url"], gym_id),
        )

    @staticmethod
    def set_image(gym_id, column, path):
        if column not in ("logo", "cover_photo"):
            raise ValueError("bad column")
        execute(f"UPDATE gyms SET {column}=%s WHERE id=%s", (path, gym_id))

    @staticmethod
    def set_open(gym_id, is_open):
        execute("UPDATE gyms SET is_open=%s WHERE id=%s", (1 if is_open else 0, gym_id))

    @staticmethod
    def set_location(gym_id, lat, lng):
        execute(
            "INSERT INTO gym_locations (gym_id, latitude, longitude) VALUES (%s,%s,%s)"
            " ON DUPLICATE KEY UPDATE latitude=VALUES(latitude), longitude=VALUES(longitude)",
            (gym_id, lat, lng),
        )

    @staticmethod
    def location(gym_id):
        return query("SELECT latitude, longitude FROM gym_locations WHERE gym_id=%s", (gym_id,), one=True)

    @staticmethod
    def set_status(gym_id, status, reason=None):
        execute("UPDATE gyms SET approval_status=%s, rejection_reason=%s WHERE id=%s", (status, reason, gym_id))

    @staticmethod
    def is_favorite(customer_id, gym_id):
        return bool(query("SELECT id FROM favorites WHERE customer_id=%s AND gym_id=%s", (customer_id, gym_id), one=True))

    @staticmethod
    def toggle_favorite(customer_id, gym_id):
        if Gym.is_favorite(customer_id, gym_id):
            execute("DELETE FROM favorites WHERE customer_id=%s AND gym_id=%s", (customer_id, gym_id))
            return False
        execute("INSERT INTO favorites (customer_id, gym_id) VALUES (%s,%s)", (customer_id, gym_id))
        return True

    @staticmethod
    def reviews(gym_id):
        return query(
            "SELECT r.*, COALESCE(CONCAT(c.first_name,' ',c.last_name),'Member') AS reviewer"
            " FROM reviews r LEFT JOIN customer_profiles c ON c.user_id=r.customer_id"
            " WHERE r.gym_id=%s AND r.product_id IS NULL ORDER BY r.created_at DESC LIMIT 20", (gym_id,))

    @staticmethod
    def can_review(customer_id, gym_id):
        return bool(query("SELECT id FROM payments WHERE customer_id=%s AND gym_id=%s AND status='paid' LIMIT 1",
                          (customer_id, gym_id), one=True))

    @staticmethod
    def add_review(customer_id, gym_id, rating, comment):
        execute("INSERT INTO reviews (customer_id, gym_id, rating, comment) VALUES (%s,%s,%s,%s)",
                (customer_id, gym_id, rating, comment))
