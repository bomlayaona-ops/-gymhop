"""Tiny database helper. Every query uses %s placeholders (safe from SQL injection)."""
import pymysql
from flask import g, current_app


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
            charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def query(sql, args=(), one=False):
    """SELECT. Returns a list of dicts, or one dict / None when one=True."""
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    if one:
        return rows[0] if rows else None
    return list(rows)


def execute(sql, args=()):
    """INSERT / UPDATE / DELETE. Returns the new row id. Call commit() when done."""
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.lastrowid


def commit():
    get_db().commit()


def rollback():
    if "db" in g:
        g.db.rollback()


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        if exc:
            conn.rollback()
        conn.close()
