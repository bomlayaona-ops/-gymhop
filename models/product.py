"""Products (merchandise and supplements) and the shopping cart."""
from db import query, execute

CATEGORIES = ["Merchandise", "Supplements", "Equipment", "Apparel"]


class Product:
    @staticmethod
    def category_id(gym_id, name):
        row = query("SELECT id FROM product_categories WHERE gym_id=%s AND name=%s", (gym_id, name), one=True)
        if row:
            return row["id"]
        return execute("INSERT INTO product_categories (gym_id, name) VALUES (%s,%s)", (gym_id, name))

    @staticmethod
    def create(gym_id, category, name, description, price, stock, image):
        return execute(
            "INSERT INTO products (gym_id, category_id, name, description, price, stock, image)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (gym_id, Product.category_id(gym_id, category), name, description, price, stock, image))

    @staticmethod
    def update(gym_id, product_id, category, name, description, price, stock, image=None):
        execute("UPDATE products SET category_id=%s, name=%s, description=%s, price=%s, stock=%s WHERE id=%s AND gym_id=%s",
                (Product.category_id(gym_id, category), name, description, price, stock, product_id, gym_id))
        if image:
            execute("UPDATE products SET image=%s WHERE id=%s AND gym_id=%s", (image, product_id, gym_id))

    @staticmethod
    def get_for_gym(gym_id, product_id):
        return query("SELECT p.*, c.name AS category FROM products p LEFT JOIN product_categories c ON c.id=p.category_id"
                     " WHERE p.id=%s AND p.gym_id=%s", (product_id, gym_id), one=True)

    @staticmethod
    def list_for_gym(gym_id, only_active=False):
        sql = ("SELECT p.*, c.name AS category FROM products p LEFT JOIN product_categories c ON c.id=p.category_id"
               " WHERE p.gym_id=%s")
        if only_active:
            sql += " AND p.is_active=1"
        return query(sql + " ORDER BY p.created_at DESC", (gym_id,))

    @staticmethod
    def delete(gym_id, product_id):
        """Delete for good. A product that already appears in an order is hidden instead (keeps order history).
        Returns True if deleted, False if it was only hidden."""
        if query("SELECT id FROM order_items WHERE product_id=%s LIMIT 1", (product_id,), one=True):
            execute("UPDATE products SET is_active=0, stock=0 WHERE id=%s AND gym_id=%s", (product_id, gym_id))
            return False
        execute("DELETE FROM products WHERE id=%s AND gym_id=%s", (product_id, gym_id))
        return True

    @staticmethod
    def toggle_active(gym_id, product_id):
        execute("UPDATE products SET is_active=1-is_active WHERE id=%s AND gym_id=%s", (product_id, gym_id))

    @staticmethod
    def shop(q="", category="", gym_id=None):
        sql = ("SELECT p.*, c.name AS category, g.name AS gym_name, g.slug AS gym_slug FROM products p"
               " JOIN gyms g ON g.id=p.gym_id LEFT JOIN product_categories c ON c.id=p.category_id"
               " WHERE p.is_active=1 AND g.approval_status='approved' AND g.is_open=1")
        args = []
        if q:
            sql += " AND (p.name LIKE %s OR g.name LIKE %s)"
            args += [f"%{q}%"] * 2
        if category:
            sql += " AND c.name=%s"
            args.append(category)
        if gym_id:
            sql += " AND p.gym_id=%s"
            args.append(gym_id)
        return query(sql + " ORDER BY p.created_at DESC", args)

    @staticmethod
    def shop_categories():
        return [r["name"] for r in query(
            "SELECT DISTINCT c.name FROM product_categories c JOIN products p ON p.category_id=c.id WHERE p.is_active=1 ORDER BY c.name")]


class Cart:
    @staticmethod
    def _cart_id(customer_id):
        row = query("SELECT id FROM carts WHERE customer_id=%s", (customer_id,), one=True)
        return row["id"] if row else execute("INSERT INTO carts (customer_id) VALUES (%s)", (customer_id,))

    @staticmethod
    def add(customer_id, product_id, qty):
        cid = Cart._cart_id(customer_id)
        execute("INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s,%s,%s)"
                " ON DUPLICATE KEY UPDATE quantity=quantity+VALUES(quantity)", (cid, product_id, qty))

    @staticmethod
    def set_qty(customer_id, product_id, qty):
        cid = Cart._cart_id(customer_id)
        if qty <= 0:
            execute("DELETE FROM cart_items WHERE cart_id=%s AND product_id=%s", (cid, product_id))
        else:
            execute("UPDATE cart_items SET quantity=%s WHERE cart_id=%s AND product_id=%s", (qty, cid, product_id))

    @staticmethod
    def items(customer_id):
        return query(
            "SELECT ci.product_id, ci.quantity, p.name, p.price, p.stock, p.image, p.is_active, p.gym_id,"
            " pc.name AS category, g.name AS gym_name, (ci.quantity*p.price) AS line_total FROM cart_items ci"
            " JOIN carts c ON c.id=ci.cart_id JOIN products p ON p.id=ci.product_id JOIN gyms g ON g.id=p.gym_id"
            " LEFT JOIN product_categories pc ON pc.id=p.category_id"
            " WHERE c.customer_id=%s ORDER BY g.name, p.name", (customer_id,))

    @staticmethod
    def clear(customer_id):
        execute("DELETE ci FROM cart_items ci JOIN carts c ON c.id=ci.cart_id WHERE c.customer_id=%s", (customer_id,))

    @staticmethod
    def count(customer_id):
        row = query("SELECT COALESCE(SUM(ci.quantity),0) AS n FROM cart_items ci JOIN carts c ON c.id=ci.cart_id"
                    " WHERE c.customer_id=%s", (customer_id,), one=True)
        return int(row["n"])
