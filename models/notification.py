"""In-app notifications."""
from db import query, execute


class Notification:
    @staticmethod
    def send(user_id, title, message, link=None):
        execute("INSERT INTO notifications (user_id, title, message, link) VALUES (%s,%s,%s,%s)",
                (user_id, title, message[:255], link))

    @staticmethod
    def notify_gym_admins(gym_id, title, message, link=None):
        for a in query("SELECT user_id FROM admin_profiles WHERE gym_id=%s", (gym_id,)):
            Notification.send(a["user_id"], title, message, link)

    @staticmethod
    def unread_count(user_id):
        return query("SELECT COUNT(*) AS n FROM notifications WHERE user_id=%s AND is_read=0", (user_id,), one=True)["n"]

    @staticmethod
    def recent(user_id, limit=50):
        return query("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user_id, limit))

    @staticmethod
    def mark_all_read(user_id):
        execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (user_id,))
