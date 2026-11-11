"""GymHop - run with:  python app.py   then open the link shown in the terminal"""
import socket
from flask import Flask, g
from config import Config
from extensions import mail, csrf
from db import close_db
from utils.security import load_current_user
from utils.uploads import product_image
from models import Cart, Notification


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    mail.init_app(app)
    csrf.init_app(app)
    app.teardown_appcontext(close_db)
    app.before_request(load_current_user)

    from routes.auth import auth, admin_auth
    from routes.main import main
    from routes.customer import customer
    from routes.admin import admin
    from routes.profile import profile
    for bp in (main, auth, admin_auth, customer, admin, profile):
        app.register_blueprint(bp)

    @app.context_processor
    def inject():
        user = g.get("user")
        cart_n = unread = 0
        if user:
            unread = Notification.unread_count(user.id)
            if user.role == "customer":
                cart_n = Cart.count(user.id)
        return {"current_user": user, "cart_count": cart_n, "unread_count": unread,
                "product_image": product_image}

    @app.template_filter("peso")
    def peso(value):
        return f"₱{float(value or 0):,.2f}"

    @app.template_filter("hhmm")
    def hhmm(value):
        """MySQL TIME comes back as a timedelta; show it as HH:MM."""
        if hasattr(value, "total_seconds"):
            secs = int(value.total_seconds())
            return f"{secs // 3600:02d}:{secs % 3600 // 60:02d}"
        return str(value)[:5]



    # There is no superadmin approval: make sure every gym is visible to customers.
    # (Fixes gyms created while the database still had the old 'draft'/'pending' default.)
    try:
        import pymysql
        conn = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                               password=Config.DB_PASSWORD, database=Config.DB_NAME)
        with conn.cursor() as cur:
            cur.execute("UPDATE gyms SET approval_status='approved' WHERE approval_status<>'approved'")
            try:   # profile photo column (added later): create it if your database does not have it yet
                cur.execute("ALTER TABLE users ADD COLUMN profile_photo VARCHAR(255) NULL")
            except pymysql.err.OperationalError:
                pass   # already exists
            cur.execute("CREATE TABLE IF NOT EXISTS gym_payment_methods ("
                        " id INT AUTO_INCREMENT PRIMARY KEY, gym_id INT NOT NULL,"
                        " method ENUM('gcash','maya','paymongo','maribank') NOT NULL,"
                        " account_name VARCHAR(120) NULL, account_number VARCHAR(40) NULL, description VARCHAR(300) NULL,"
                        " qr_image VARCHAR(255) NULL, is_enabled TINYINT(1) NOT NULL DEFAULT 1,"
                        " UNIQUE KEY uq_gym_method (gym_id, method),"
                        " FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE)")
            cur.execute("ALTER TABLE payments MODIFY method ENUM('gcash','maya','cash_onsite','paymongo','maribank','other') NOT NULL")
        conn.commit()
        conn.close()
    except Exception as e:
        print("Could not reach MySQL on port", Config.DB_PORT, "- is XAMPP MySQL running?", e)

    return app


app = create_app()

def lan_ip():
    """This computer's address on your Wi-Fi/network (for opening on a phone or another browser)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


if __name__ == "__main__":
    PORT = 5000
    ip = lan_ip()
    print("\n  GymHop is running. Open one of these links (Ctrl+Click):")
    print(f"    Local:    http://127.0.0.1:{PORT}")
    if ip:
        print(f"    Network:  http://{ip}:{PORT}   (other browser / phone on the same Wi-Fi)")
    print()
    app.run(host="0.0.0.0", debug=True, port=PORT)
