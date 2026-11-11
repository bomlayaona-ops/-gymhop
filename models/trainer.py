"""Trainers and trainer bookings."""
from db import query, execute


class Trainer:
    @staticmethod
    def list_for_gym(gym_id, only_available=False):
        sql = "SELECT * FROM trainers WHERE gym_id=%s"
        if only_available:
            sql += " AND is_available=1"
        return query(sql + " ORDER BY full_name", (gym_id,))

    @staticmethod
    def get(trainer_id):
        return query("SELECT * FROM trainers WHERE id=%s", (trainer_id,), one=True)

    @staticmethod
    def get_for_gym(gym_id, trainer_id):
        return query("SELECT * FROM trainers WHERE id=%s AND gym_id=%s", (trainer_id, gym_id), one=True)

    @staticmethod
    def create(gym_id, full_name, specialization, experience_years, description, rate, availability, image):
        return execute(
            "INSERT INTO trainers (gym_id, full_name, specialization, experience_years, description,"
            " rate_per_session, availability, profile_image) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (gym_id, full_name, specialization, experience_years, description, rate, availability, image))

    @staticmethod
    def update(gym_id, trainer_id, full_name, specialization, experience_years, description, rate, availability, image=None):
        execute("UPDATE trainers SET full_name=%s, specialization=%s, experience_years=%s, description=%s,"
                " rate_per_session=%s, availability=%s WHERE id=%s AND gym_id=%s",
                (full_name, specialization, experience_years, description, rate, availability, trainer_id, gym_id))
        if image:
            execute("UPDATE trainers SET profile_image=%s WHERE id=%s AND gym_id=%s", (image, trainer_id, gym_id))

    @staticmethod
    def delete(gym_id, trainer_id):
        """True if deleted; False if the trainer has bookings (then only hidden, so booking history stays)."""
        if query("SELECT id FROM trainer_bookings WHERE trainer_id=%s LIMIT 1", (trainer_id,), one=True):
            execute("UPDATE trainers SET is_available=0 WHERE id=%s AND gym_id=%s", (trainer_id, gym_id))
            return False
        execute("DELETE FROM trainers WHERE id=%s AND gym_id=%s", (trainer_id, gym_id))
        return True

    @staticmethod
    def toggle_available(gym_id, trainer_id):
        execute("UPDATE trainers SET is_available=1-is_available WHERE id=%s AND gym_id=%s", (trainer_id, gym_id))


class Booking:
    @staticmethod
    def slot_taken(trainer_id, session_date, session_time):
        return bool(query("SELECT id FROM trainer_bookings WHERE trainer_id=%s AND session_date=%s AND session_time=%s"
                          " AND status<>'cancelled'", (trainer_id, session_date, session_time), one=True))

    @staticmethod
    def create(customer_id, trainer, session_date, session_time, notes):
        return execute(
            "INSERT INTO trainer_bookings (customer_id, trainer_id, gym_id, session_date, session_time, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s)",
            (customer_id, trainer["id"], trainer["gym_id"], session_date, session_time, notes))

    @staticmethod
    def get_for_gym(gym_id, booking_id):
        return query("SELECT * FROM trainer_bookings WHERE id=%s AND gym_id=%s", (booking_id, gym_id), one=True)

    @staticmethod
    def set_status(booking_id, status):
        execute("UPDATE trainer_bookings SET status=%s WHERE id=%s", (status, booking_id))

    @staticmethod
    def for_customer(customer_id):
        return query(
            "SELECT b.*, t.full_name AS trainer_name, t.rate_per_session, g.name AS gym_name, g.slug AS gym_slug,"
            " (SELECT status FROM payments p WHERE p.booking_id=b.id LIMIT 1) AS payment_status"
            " FROM trainer_bookings b JOIN trainers t ON t.id=b.trainer_id JOIN gyms g ON g.id=b.gym_id"
            " WHERE b.customer_id=%s ORDER BY b.session_date DESC, b.session_time DESC", (customer_id,))

    @staticmethod
    def for_gym(gym_id):
        return query(
            "SELECT b.*, t.full_name AS trainer_name, t.rate_per_session, c.first_name, c.last_name, u.email,"
            " (SELECT status FROM payments p WHERE p.booking_id=b.id LIMIT 1) AS payment_status"
            " FROM trainer_bookings b JOIN trainers t ON t.id=b.trainer_id JOIN users u ON u.id=b.customer_id"
            " LEFT JOIN customer_profiles c ON c.user_id=b.customer_id"
            " WHERE b.gym_id=%s ORDER BY b.session_date DESC, b.session_time DESC", (gym_id,))
