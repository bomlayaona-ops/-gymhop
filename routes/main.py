"""Public pages: home, gyms, gym page, shop, reviews, favorites."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from db import commit
from models import Gym, Product, MembershipPlan, Trainer, Cart
from utils.security import login_required

main = Blueprint("main", __name__)


@main.route("/")
def home():
    """Visitors who are not logged in only see the public landing page (index.html)."""
    if not g.get("user"):
        return render_template("index.html")
    if g.user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    gyms = Gym.search()[:6]
    products = Product.shop()[:8]
    return render_template("home.html", gyms=gyms, products=products, cities=Gym.cities())


@main.route("/gyms")
@login_required("customer", "admin")
def gyms():
    q = request.args.get("q", "").strip()
    city = request.args.get("city", "").strip()
    province = request.args.get("province", "").strip()
    only_open = request.args.get("open") == "1"
    return render_template("gyms.html", gyms=Gym.search(q, city, only_open, province), q=q, city=city,
                           province=province, only_open=only_open, cities=Gym.cities(), provinces=Gym.provinces())


@main.route("/gym/<slug>")
@login_required("customer", "admin")
def gym_detail(slug):
    gym = Gym.get_public(slug)
    if not gym:
        abort(404)
    user = g.user
    products = Product.list_for_gym(gym["id"], only_active=True)
    for p in products:
        p["gym_name"], p["gym_slug"] = gym["name"], gym["slug"]
    return render_template(
        "gym_detail.html", gym=gym, location=Gym.location(gym["id"]),
        plans=MembershipPlan.list_for_gym(gym["id"], only_active=True),
        trainers=Trainer.list_for_gym(gym["id"], only_available=True),
        products=products,
        reviews=Gym.reviews(gym["id"]),
        is_favorite=bool(user and user.role == "customer" and Gym.is_favorite(user.id, gym["id"])),
        can_review=bool(user and user.role == "customer" and Gym.can_review(user.id, gym["id"])))


@main.route("/shop")
@login_required("customer", "admin")
def shop():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    return render_template("shop.html", products=Product.shop(q, category), q=q, category=category,
                           categories=Product.shop_categories())


@main.route("/gym/<int:gym_id>/favorite", methods=["POST"])
@login_required("customer")
def favorite(gym_id):
    gym = Gym.get(gym_id)
    if not gym or gym["approval_status"] != "approved":
        abort(404)
    added = Gym.toggle_favorite(g.user.id, gym_id)
    commit()
    flash("Saved to your favorites." if added else "Removed from favorites.", "success")
    return redirect(url_for("main.gym_detail", slug=gym["slug"]))


@main.route("/gym/<int:gym_id>/review", methods=["POST"])
@login_required("customer")
def review(gym_id):
    gym = Gym.get(gym_id)
    if not gym or gym["approval_status"] != "approved":
        abort(404)
    if not Gym.can_review(g.user.id, gym_id):
        flash("You can review a gym after your first confirmed payment there.", "warning")
        return redirect(url_for("main.gym_detail", slug=gym["slug"]))
    try:
        rating = int(request.form.get("rating", "0"))
    except ValueError:
        rating = 0
    if not 1 <= rating <= 5:
        flash("Choose a rating from 1 to 5.", "danger")
    else:
        Gym.add_review(g.user.id, gym_id, rating, request.form.get("comment", "").strip()[:1000])
        commit()
        flash("Thanks for your review!", "success")
    return redirect(url_for("main.gym_detail", slug=gym["slug"]))
