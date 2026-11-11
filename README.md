# GymHop — Find Your Gym. Build Your Strength.

A multi-gym marketplace (Shopee/Lazada style, gym theme) built with **Flask, HTML, CSS, JavaScript and MySQL (XAMPP)**.

* **Customers** browse gyms, see if a gym is open, join a membership, book a trainer, and buy merch/supplements.
* **Gym admins** each get their own account + gym storefront and only ever see their own records.
* A new gym goes live as soon as its owner registers (no approval step).

## Features you asked for
| Feature | Where |
|---|---|
| Optional product photo, with a default picture (e.g. a creatine tub for *Supplements*) that the admin can replace or remove | Admin → Products |
| Eye button to show/hide the password | Login + register pages (customer and admin) |
| GCash / Maya / cash payment with reference number + optional screenshot; admin confirms it | Checkout, Join, Book trainer → Admin → Payments |
| 6-digit code emailed on every login (expires in 10 minutes, 5 tries) | Both logins |

## 1. Set up the database (XAMPP)
1. Open XAMPP Control Panel → **Start Apache and MySQL**.
2. Go to http://localhost/phpmyadmin → **Import** tab → choose `database.sql` → **Go**.
   This creates the database `gymhop_marketplace` with every table.

## 2. Install and run
```bash
cd GymHop
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env
```
Open `.env` and fill it in (see below), then:
```bash
python app.py
```
Open http://127.0.0.1:5000

If your XAMPP MySQL uses port 3307, set `DB_PORT=3307` in `.env`.

## 3. Email codes (Gmail)
1. Google Account → Security → turn on **2-Step Verification**.
2. Security → **App passwords** → create one → paste it as `MAIL_PASSWORD` in `.env` (no spaces).
3. Put your Gmail in `MAIL_USERNAME` and `MAIL_DEFAULT_SENDER`.

> Until `MAIL_USERNAME` / `MAIL_PASSWORD` are filled in, the app runs in **developer mode**: the code is
> shown on the verify page and printed in the terminal so you can test. **Fill in the mail settings before
> real use** — developer mode must not be used on a public site.

## 4. Try the whole flow
1. `/admin/register` → create a gym account → `/admin/login` → enter the emailed code → your dashboard opens.
2. In the dashboard → **My gym** (hours, map pin, open/closed) → add **Products**, **Memberships**, **Trainers**.
3. `/register` → customer account → log in → open the gym → add to cart / join / book.
4. Back in the admin → **Payments** → check the GCash reference → **Confirm**. The membership/order/booking activates.

## Folder structure
```
GymHop/
├── app.py                 start here (creates the Flask app)
├── config.py              reads .env
├── db.py                  database connection helper (PyMySQL)
├── extensions.py          Flask-Mail and CSRF protection
├── database.sql           import in phpMyAdmin
├── requirements.txt  .env.example
├── models/                OOP classes: User/Customer/Admin/SuperAdmin, Gym, Product, Cart,
│                          MembershipPlan, Membership, Trainer, Booking, Order, Payment, Notification
├── routes/                auth.py  main.py  customer.py  admin.py
├── utils/                 security.py (login/roles)  uploads.py (safe images + defaults)  mailer.py (email code)
├── templates/             auth/  customer/  admin/  partials/
└── static/                css/style.css + extra.css · js/main.js · images/ (logo, hero, defaults/) · uploads/
```

## Pages
* **Login comes first.** Anyone who is not logged in only sees the welcome page: a greeting, what GymHop is, and the Login | Register tabs. The marketplace, shop, cart and dashboards open only after logging in.
* Customers: `/login` and `/register` (two tabs), then the marketplace, cart, My activity.
* Gym owners: `/admin/login` and `/admin/register` (two tabs), then `/admin/` dashboard.
* Opening any other page while logged out sends you to the login page (gym owner pages go to the gym owner login).

## Security built in
Hashed passwords, CSRF tokens on every form, parameterized SQL, role checks on every page, each admin
limited to their own gym, image uploads verified with Pillow, 5 MB upload limit, email login codes.

## Not included (be upfront in your presentation)
No automatic GCash/Maya verification — the gym admin confirms payments by hand after checking their wallet.
Add a payment gateway (e.g. PayMongo) if you need automatic confirmation. No password-reset page yet.
Set `debug=False` and a strong `SECRET_KEY` before deploying.

## Put it on GitHub and make it live

1. Never upload `.env` (it holds your Gmail App Password). `.gitignore` already blocks it.
2. `git init`, `git add .`, `git commit -m "GymHop"`, then create an empty repo on github.com and run
   `git remote add origin <repo-url>`, `git branch -M main`, `git push -u origin main`.
3. GitHub only stores the code. To run it online use a Python host with MySQL (e.g. PythonAnywhere):
   clone the repo, create a virtualenv, `pip install -r requirements.txt`, create a MySQL database,
   import `database.sql`, set SECRET_KEY / DB_* / MAIL_* as environment variables, point the WSGI file at `wsgi.py`, and reload.
