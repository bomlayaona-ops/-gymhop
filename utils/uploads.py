"""Safe image uploads. Images are optional everywhere."""
import os
import secrets
from flask import current_app
from PIL import Image

ALLOWED = {"png", "jpg", "jpeg", "webp"}

# Default pictures used when an admin does not upload one (file names inside static/images/defaults/)
DEFAULT_PRODUCT_IMAGES = {
    "Supplements": "images/defaults/supplement.svg",   # creatine tub
    "Merchandise": "images/defaults/merch.svg",
    "Equipment": "images/defaults/equipment.svg",
    "Apparel": "images/defaults/apparel.svg",
}


def save_image(file, folder):
    """Save an uploaded image. Returns 'uploads/<folder>/<name>' or None if no file was chosen.
    Raises ValueError for bad files."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED:
        raise ValueError("Only PNG, JPG or WEBP images are allowed.")
    try:
        img = Image.open(file.stream)
        img.verify()            # is it really an image?
        file.stream.seek(0)
    except Exception:
        raise ValueError("That file is not a valid image.")
    name = f"{secrets.token_hex(12)}.{ext}"
    target = os.path.join(current_app.config["UPLOAD_ROOT"], folder)
    os.makedirs(target, exist_ok=True)
    file.save(os.path.join(target, name))
    return f"uploads/{folder}/{name}"


def product_image(product):
    """Path (relative to /static) to show for a product: its own photo, or a default for its category."""
    if product.get("image"):
        return product["image"]
    return DEFAULT_PRODUCT_IMAGES.get(product.get("category"), "images/defaults/default.svg")
