"""Product orders. A checkout with items from several gyms is split into one order per gym."""
import secrets
from datetime import datetime
from decimal import Decimal
from db import query, execute


class Order:
    @staticmethod
    def new_number():
        return f"GH-{datetime.utcnow():%y%m%d}-{secrets.token_hex(3).upper()}"

    @staticmethod
    def create_for_gym(customer_id, gym_id, items, address):
        """items = list of cart rows for ONE gym. Reduces stock. Returns (order_id, total)."""
        total = sum(Decimal(str(i["price"])) * i["quantity"] for i in items)
        order_id = execute(
            "INSERT INTO product_orders (order_number, customer_id, gym_id, total_amount, shipping_address)"
            " VALUES (%s,%s,%s,%s,%s)", (Order.new_number(), customer_id, gym_id, total, address))
        for i in items:
            execute("INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity)"
                    " VALUES (%s,%s,%s,%s,%s)", (order_id, i["product_id"], i["name"], i["price"], i["quantity"]))
            execute("UPDATE products SET stock=stock-%s WHERE id=%s", (i["quantity"], i["product_id"]))
        return order_id, total

    @staticmethod
    def restore_stock(order_id):
        for it in query("SELECT product_id, quantity FROM order_items WHERE order_id=%s", (order_id,)):
            execute("UPDATE products SET stock=stock+%s WHERE id=%s", (it["quantity"], it["product_id"]))

    @staticmethod
    def get_for_gym(gym_id, order_id):
        return query("SELECT * FROM product_orders WHERE id=%s AND gym_id=%s", (order_id, gym_id), one=True)

    @staticmethod
    def set_status(order_id, status):
        execute("UPDATE product_orders SET status=%s WHERE id=%s", (status, order_id))

    @staticmethod
    def items(order_id):
        return query("SELECT * FROM order_items WHERE order_id=%s", (order_id,))

    @staticmethod
    def for_customer(customer_id):
        rows = query(
            "SELECT o.*, g.name AS gym_name, g.slug AS gym_slug,"
            " (SELECT status FROM payments p WHERE p.order_id=o.id LIMIT 1) AS payment_status"
            " FROM product_orders o JOIN gyms g ON g.id=o.gym_id WHERE o.customer_id=%s ORDER BY o.created_at DESC",
            (customer_id,))
        for r in rows:
            r["items"] = Order.items(r["id"])
        return rows

    @staticmethod
    def for_gym(gym_id):
        rows = query(
            "SELECT o.*, c.first_name, c.last_name, u.email,"
            " (SELECT status FROM payments p WHERE p.order_id=o.id LIMIT 1) AS payment_status"
            " FROM product_orders o JOIN users u ON u.id=o.customer_id"
            " LEFT JOIN customer_profiles c ON c.user_id=o.customer_id WHERE o.gym_id=%s ORDER BY o.created_at DESC",
            (gym_id,))
        for r in rows:
            r["items"] = Order.items(r["id"])
        return rows
