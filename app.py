"""
Jewellery Shop - Flask Backend
Three-tier: Nginx (reverse proxy) → Flask/Gunicorn → AWS RDS MySQL
"""

import os
import time
import requests
from datetime import timedelta, timezone, datetime
from functools import wraps

import bcrypt
import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt_identity, verify_jwt_in_request
)

load_dotenv()

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config["SECRET_KEY"]                   = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config["JWT_SECRET_KEY"]               = os.getenv("JWT_SECRET_KEY",   "dev-jwt-secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"]     = timedelta(hours=12)
app.config["JWT_TOKEN_LOCATION"]           = ["headers"]
app.config["JWT_HEADER_NAME"]              = "Authorization"
app.config["JWT_HEADER_TYPE"]              = "Bearer"

jwt = JWTManager(app)


# ── DB connection ────────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host     = os.getenv("DB_HOST",     "127.0.0.1"),
            port     = int(os.getenv("DB_PORT", 3306)),
            user     = os.getenv("DB_USER",     "root"),
            password = os.getenv("DB_PASSWORD", ""),
            database = os.getenv("DB_NAME",     "jewellery_shop"),
            charset  = "utf8mb4",
            cursorclass = pymysql.cursors.DictCursor,
            autocommit  = True,
        )
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def query(sql, args=None, one=False):
    cur = get_db().cursor()
    cur.execute(sql, args or ())
    result = cur.fetchone() if one else cur.fetchall()
    cur.close()
    return result


def execute(sql, args=None):
    cur = get_db().cursor()
    cur.execute(sql, args or ())
    last_id = cur.lastrowid
    cur.close()
    return last_id


# ── Helpers ──────────────────────────────────────────────────────────────────
def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_pw(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def calc_price(weight: float, price_per_gram: float,
               making: float, stone: float) -> float:
    return round(weight * price_per_gram + making + stone, 2)


def get_latest_prices() -> dict:
    rows = query("""
        SELECT mp.metal_type, mp.price_per_gram, mp.fetched_at
        FROM metal_prices mp
        INNER JOIN (
            SELECT metal_type, MAX(fetched_at) AS max_ts
            FROM metal_prices GROUP BY metal_type
        ) latest ON mp.metal_type = latest.metal_type
                AND mp.fetched_at  = latest.max_ts
    """)
    return {r["metal_type"]: r for r in rows}


# ── Metal price refresh (called periodically or on demand) ───────────────────
def refresh_metal_prices():
    """
    Fetch live gold/silver prices via a public API.
    Falls back silently to DB values if API is unavailable.
    Replace the URL/key with your preferred provider.
    """
    api_key = os.getenv("METAL_PRICE_API_KEY", "")
    if not api_key:
        return

    try:
        url = f"https://metals-api.com/api/latest?access_key={api_key}&base=INR&symbols=XAU,XAG,XPT"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("success"):
            rates = data["rates"]
            # metals-api returns price per troy-oz; convert to per-gram
            # 1 troy oz = 31.1035 g
            mapping = {
                "gold":      1 / (rates.get("XAU", 1) / 31.1035),
                "silver":    1 / (rates.get("XAG", 1) / 31.1035),
                "platinum":  1 / (rates.get("XPT", 1) / 31.1035),
            }
            for metal, pgram in mapping.items():
                execute(
                    "INSERT INTO metal_prices (metal_type, price_per_gram, source) VALUES (%s, %s, %s)",
                    (metal, round(pgram, 4), "metals-api")
                )
    except Exception:
        pass   # silently keep existing DB prices


# ════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name   = (data.get("name")   or "").strip()
    email  = (data.get("email")  or "").strip().lower()
    mobile = (data.get("mobile") or "").strip()
    budget = data.get("budget", 0)
    pwd    = data.get("password", "")

    if not all([name, email, mobile, pwd]):
        return jsonify({"error": "name, email, mobile and password are required"}), 400
    if len(pwd) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if query("SELECT id FROM clients WHERE email=%s", (email,), one=True):
        return jsonify({"error": "Email already registered"}), 409

    try:
        budget = float(budget)
    except (ValueError, TypeError):
        budget = 0.0

    client_id = execute(
        "INSERT INTO clients (name, email, mobile, password_hash, budget) VALUES (%s,%s,%s,%s,%s)",
        (name, email, mobile, hash_pw(pwd), budget)
    )
    # Create empty cart
    execute("INSERT INTO carts (client_id) VALUES (%s)", (client_id,))

    token = create_access_token(identity=str(client_id))
    return jsonify({
        "message": "Registration successful",
        "token":   token,
        "client":  {"id": client_id, "name": name, "email": email,
                    "mobile": mobile, "budget": budget}
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data   = request.get_json(silent=True) or {}
    email  = (data.get("email")  or "").strip().lower()
    pwd    = data.get("password", "")

    client = query("SELECT * FROM clients WHERE email=%s", (email,), one=True)
    if not client or not check_pw(pwd, client["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(client["id"]))
    return jsonify({
        "message": "Login successful",
        "token":   token,
        "client":  {
            "id":     client["id"],
            "name":   client["name"],
            "email":  client["email"],
            "mobile": client["mobile"],
            "budget": float(client["budget"]),
        }
    })


@app.route("/api/auth/profile", methods=["GET"])
@jwt_required()
def profile():
    uid = int(get_jwt_identity())
    client = query("SELECT id,name,email,mobile,budget,created_at FROM clients WHERE id=%s",
                   (uid,), one=True)
    if not client:
        return jsonify({"error": "User not found"}), 404
    client["budget"]     = float(client["budget"])
    client["created_at"] = str(client["created_at"])
    return jsonify(client)


@app.route("/api/auth/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    uid  = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name   = (data.get("name")   or "").strip()
    mobile = (data.get("mobile") or "").strip()
    budget = data.get("budget")

    try:
        budget = float(budget) if budget is not None else None
    except (ValueError, TypeError):
        budget = None

    if name:
        execute("UPDATE clients SET name=%s WHERE id=%s",   (name, uid))
    if mobile:
        execute("UPDATE clients SET mobile=%s WHERE id=%s", (mobile, uid))
    if budget is not None:
        execute("UPDATE clients SET budget=%s WHERE id=%s", (budget, uid))

    return jsonify({"message": "Profile updated"})


# ════════════════════════════════════════════════════════════════════════════
# CATALOGUE ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/categories", methods=["GET"])
def categories():
    cats = query("SELECT id, name, description, icon FROM categories ORDER BY name")
    return jsonify(cats)


@app.route("/api/items", methods=["GET"])
def items():
    refresh_metal_prices()         # attempt live refresh on every catalogue call
    prices = get_latest_prices()

    category_id = request.args.get("category_id")
    search      = request.args.get("search", "").strip()

    sql  = "SELECT * FROM jewellery_items WHERE is_active=1"
    args = []

    if category_id:
        sql += " AND category_id=%s"
        args.append(category_id)
    if search:
        sql += " AND name LIKE %s"
        args.append(f"%{search}%")

    sql += " ORDER BY created_at DESC"
    rows = query(sql, args)

    cats = {c["id"]: c["name"] for c in query("SELECT id, name FROM categories")}

    result = []
    for r in rows:
        metal = r["metal_type"]
        ppg   = float(prices[metal]["price_per_gram"]) if metal in prices else 0
        total = calc_price(float(r["weight_grams"]), ppg,
                           float(r["making_charges"]), float(r["stone_charges"]))
        result.append({
            "id":            r["id"],
            "name":          r["name"],
            "description":   r["description"],
            "metal_type":    metal,
            "metal_purity":  r["metal_purity"],
            "weight_grams":  float(r["weight_grams"]),
            "making_charges":float(r["making_charges"]),
            "stone_charges": float(r["stone_charges"]),
            "image_url":     r["image_url"],
            "stock":         r["stock"],
            "category_id":   r["category_id"],
            "category_name": cats.get(r["category_id"], ""),
            "price_per_gram":ppg,
            "total_price":   total,
        })
    return jsonify(result)


@app.route("/api/items/<int:item_id>", methods=["GET"])
def item_detail(item_id):
    prices = get_latest_prices()
    r = query("SELECT * FROM jewellery_items WHERE id=%s AND is_active=1",
              (item_id,), one=True)
    if not r:
        return jsonify({"error": "Item not found"}), 404

    metal = r["metal_type"]
    ppg   = float(prices[metal]["price_per_gram"]) if metal in prices else 0
    total = calc_price(float(r["weight_grams"]), ppg,
                       float(r["making_charges"]), float(r["stone_charges"]))

    cat = query("SELECT name FROM categories WHERE id=%s", (r["category_id"],), one=True)
    return jsonify({
        **{k: (float(v) if isinstance(v, __builtins__.__class__) else v)
           for k, v in r.items()},
        "price_per_gram":  ppg,
        "total_price":     total,
        "category_name":   cat["name"] if cat else "",
    })


@app.route("/api/prices", methods=["GET"])
def live_prices():
    refresh_metal_prices()
    prices = get_latest_prices()
    return jsonify({
        metal: {
            "price_per_gram": float(info["price_per_gram"]),
            "updated_at":     str(info["fetched_at"]),
        }
        for metal, info in prices.items()
    })


# ════════════════════════════════════════════════════════════════════════════
# CART ROUTES
# ════════════════════════════════════════════════════════════════════════════

def _ensure_cart(client_id: int) -> int:
    cart = query("SELECT id FROM carts WHERE client_id=%s", (client_id,), one=True)
    if cart:
        return cart["id"]
    return execute("INSERT INTO carts (client_id) VALUES (%s)", (client_id,))


def _cart_response(client_id: int):
    prices = get_latest_prices()
    cart_id = _ensure_cart(client_id)
    rows = query("""
        SELECT ci.id AS cart_item_id, ci.quantity, ci.price_snapshot, ci.added_at,
               ji.id AS item_id, ji.name, ji.image_url, ji.metal_type,
               ji.metal_purity, ji.weight_grams, ji.making_charges, ji.stone_charges
        FROM cart_items ci
        JOIN jewellery_items ji ON ji.id = ci.item_id
        WHERE ci.cart_id=%s
        ORDER BY ci.added_at DESC
    """, (cart_id,))

    items_out = []
    cart_total = 0.0
    for r in rows:
        metal = r["metal_type"]
        ppg   = float(prices[metal]["price_per_gram"]) if metal in prices else 0
        live  = calc_price(float(r["weight_grams"]), ppg,
                           float(r["making_charges"]), float(r["stone_charges"]))
        line  = live * r["quantity"]
        cart_total += line
        items_out.append({
            "cart_item_id":  r["cart_item_id"],
            "item_id":       r["item_id"],
            "name":          r["name"],
            "image_url":     r["image_url"],
            "metal_type":    metal,
            "metal_purity":  r["metal_purity"],
            "quantity":      r["quantity"],
            "unit_price":    live,
            "line_total":    round(line, 2),
            "added_at":      str(r["added_at"]),
        })

    client = query("SELECT budget FROM clients WHERE id=%s", (client_id,), one=True)
    budget = float(client["budget"]) if client else 0

    return {
        "cart_id":    cart_id,
        "items":      items_out,
        "cart_total": round(cart_total, 2),
        "budget":     budget,
        "within_budget": cart_total <= budget,
    }


@app.route("/api/cart", methods=["GET"])
@jwt_required()
def get_cart():
    uid = int(get_jwt_identity())
    return jsonify(_cart_response(uid))


@app.route("/api/cart/add", methods=["POST"])
@jwt_required()
def add_to_cart():
    uid     = int(get_jwt_identity())
    data    = request.get_json(silent=True) or {}
    item_id = data.get("item_id")
    qty     = int(data.get("quantity", 1))

    if not item_id:
        return jsonify({"error": "item_id required"}), 400

    item = query("SELECT * FROM jewellery_items WHERE id=%s AND is_active=1",
                 (item_id,), one=True)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item["stock"] < qty:
        return jsonify({"error": "Insufficient stock"}), 400

    prices = get_latest_prices()
    metal  = item["metal_type"]
    ppg    = float(prices[metal]["price_per_gram"]) if metal in prices else 0
    price  = calc_price(float(item["weight_grams"]), ppg,
                        float(item["making_charges"]), float(item["stone_charges"]))

    cart_id = _ensure_cart(uid)
    existing = query("SELECT id, quantity FROM cart_items WHERE cart_id=%s AND item_id=%s",
                     (cart_id, item_id), one=True)
    if existing:
        new_qty = existing["quantity"] + qty
        execute("UPDATE cart_items SET quantity=%s, price_snapshot=%s WHERE id=%s",
                (new_qty, price, existing["id"]))
    else:
        execute("INSERT INTO cart_items (cart_id, item_id, quantity, price_snapshot) VALUES (%s,%s,%s,%s)",
                (cart_id, item_id, qty, price))

    return jsonify({"message": "Added to cart", "cart": _cart_response(uid)}), 201


@app.route("/api/cart/update/<int:cart_item_id>", methods=["PUT"])
@jwt_required()
def update_cart_item(cart_item_id):
    uid  = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    qty  = int(data.get("quantity", 1))

    cart_id = _ensure_cart(uid)
    ci = query("SELECT * FROM cart_items WHERE id=%s AND cart_id=%s",
               (cart_item_id, cart_id), one=True)
    if not ci:
        return jsonify({"error": "Cart item not found"}), 404

    if qty <= 0:
        execute("DELETE FROM cart_items WHERE id=%s", (cart_item_id,))
    else:
        execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (qty, cart_item_id))

    return jsonify({"message": "Cart updated", "cart": _cart_response(uid)})


@app.route("/api/cart/remove/<int:cart_item_id>", methods=["DELETE"])
@jwt_required()
def remove_cart_item(cart_item_id):
    uid     = int(get_jwt_identity())
    cart_id = _ensure_cart(uid)
    execute("DELETE FROM cart_items WHERE id=%s AND cart_id=%s", (cart_item_id, cart_id))
    return jsonify({"message": "Item removed", "cart": _cart_response(uid)})


@app.route("/api/cart/clear", methods=["DELETE"])
@jwt_required()
def clear_cart():
    uid     = int(get_jwt_identity())
    cart_id = _ensure_cart(uid)
    execute("DELETE FROM cart_items WHERE cart_id=%s", (cart_id,))
    return jsonify({"message": "Cart cleared"})


# ════════════════════════════════════════════════════════════════════════════
# ORDER ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/orders", methods=["POST"])
@jwt_required()
def place_order():
    uid  = int(get_jwt_identity())
    data = _cart_response(uid)

    if not data["items"]:
        return jsonify({"error": "Cart is empty"}), 400

    total    = data["cart_total"]
    order_id = execute(
        "INSERT INTO orders (client_id, total_amount, status) VALUES (%s,%s,'confirmed')",
        (uid, total)
    )
    for ci in data["items"]:
        execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (%s,%s,%s,%s)",
            (order_id, ci["item_id"], ci["quantity"], ci["unit_price"])
        )
        execute(
            "UPDATE jewellery_items SET stock = stock - %s WHERE id=%s",
            (ci["quantity"], ci["item_id"])
        )

    cart_id = _ensure_cart(uid)
    execute("DELETE FROM cart_items WHERE cart_id=%s", (cart_id,))

    return jsonify({"message": "Order placed successfully", "order_id": order_id,
                    "total": total}), 201


@app.route("/api/orders", methods=["GET"])
@jwt_required()
def my_orders():
    uid    = int(get_jwt_identity())
    orders = query("""
        SELECT o.id, o.total_amount, o.status, o.created_at,
               COUNT(oi.id) AS item_count
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.client_id=%s
        GROUP BY o.id ORDER BY o.created_at DESC
    """, (uid,))
    for o in orders:
        o["total_amount"] = float(o["total_amount"])
        o["created_at"]   = str(o["created_at"])
    return jsonify(orders)


# ════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    try:
        get_db().ping(reconnect=True)
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({
        "status": "ok" if db_ok else "degraded",
        "db":     "connected" if db_ok else "error",
        "ts":     datetime.now(timezone.utc).isoformat(),
    }), 200 if db_ok else 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
