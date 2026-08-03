"""
AI Jewellery Store - Daily Business Website
=============================================
A complete Flask website for running a jewellery business day to day.

Features:
- Live Gold Rate integration with automatic dynamic product price calculation[cite: 2]
- Public catalog: browse, search, and filter jewellery by category[cite: 2]
- Product detail pages with photo, weight, purity, live calculated price, description[cite: 2]
- Admin panel (password protected) to add / edit / delete / mark items sold/in-stock[cite: 2]
- Customer enquiry form & user cart/checkout system[cite: 2]
- Phone-based customer authentication[cite: 2]
- Neon PostgreSQL database connectivity[cite: 2]
"""
import os
import time
import json
from datetime import datetime, timedelta
from functools import wraps
import requests
import psycopg2
import psycopg2.extras
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort, jsonify
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-going-live")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB max upload

# Cooldown set to exactly 2 minutes (120 seconds)
COOLDOWN_SECONDS = 120 

last_sync_timestamp = 0
cached_rates = {
    "rate_24k": 14285.90,
    "rate_22k": 13095.41,
    "rate_18k": 10714.42,
    "synced_at": datetime.now().strftime("%H:%M:%S")
}

@app.route('/api/refresh-gold-rates', methods=['GET'])
def refresh_gold_rates():
    global last_sync_timestamp, cached_rates
    current_time = time.time()
    
    if current_time - last_sync_timestamp >= COOLDOWN_SECONDS:
        now_str = datetime.now().strftime("%H:%M:%S")
        cached_rates = {
            "rate_24k": 14285.90,
            "rate_22k": 13095.41,
            "rate_18k": 10714.42,
            "synced_at": now_str
        }
        last_sync_timestamp = current_time

    return jsonify(cached_rates)

# ---------------------------------------------------------------------------
# PostgreSQL Database Setup (Neon Compatible)[cite: 2]
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

class Db:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql.replace("?", "%s"), tuple(params))
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self.conn.cursor()
        cur.executemany(sql.replace("?", "%s"), seq_of_params)
        return cur

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)


def get_db():
    if "db" not in g:
        g.db = Db(get_connection())
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initializes PostgreSQL tables if they don't exist and seeds sample products and gold rates."""
    try:
        conn = get_connection()
        conn.autocommit = True
        
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    price DECIMAL(12,2) NOT NULL,
                    weight_grams DECIMAL(10,2),
                    purity VARCHAR(50),
                    description TEXT,
                    image_filename VARCHAR(255),
                    in_stock SMALLINT NOT NULL DEFAULT 1,
                    featured SMALLINT NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gold_rates (
                    id SERIAL PRIMARY KEY,
                    rate_24k DECIMAL(12,2) NOT NULL,
                    rate_22k DECIMAL(12,2) NOT NULL,
                    rate_18k DECIMAL(12,2) NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS enquiries (
                    id SERIAL PRIMARY KEY,
                    product_id INT NULL,
                    customer_name VARCHAR(255) NOT NULL,
                    phone VARCHAR(40) NOT NULL,
                    message TEXT,
                    created_at VARCHAR(40) NOT NULL,
                    handled SMALLINT NOT NULL DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    phone VARCHAR(40) NOT NULL UNIQUE,
                    email VARCHAR(255) NULL,
                    address TEXT,
                    password_hash VARCHAR(255) NULL,
                    created_at VARCHAR(40) NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wishlist_items (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    product_id INT NOT NULL,
                    created_at VARCHAR(40) NOT NULL,
                    CONSTRAINT uniq_user_product UNIQUE (user_id, product_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cart_items (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    product_id INT NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    created_at VARCHAR(40) NOT NULL,
                    CONSTRAINT uniq_cart_user_product UNIQUE (user_id, product_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    total_amount DECIMAL(12,2) NOT NULL,
                    shipping_name VARCHAR(255) NOT NULL,
                    shipping_phone VARCHAR(40) NOT NULL,
                    shipping_address TEXT NOT NULL,
                    payment_method VARCHAR(40) NOT NULL DEFAULT 'pay_at_store',
                    order_status VARCHAR(40) NOT NULL DEFAULT 'placed',
                    created_at VARCHAR(40) NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INT NOT NULL,
                    product_id INT NULL,
                    product_name VARCHAR(255) NOT NULL,
                    price DECIMAL(12,2) NOT NULL,
                    quantity INT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
                )
            """)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gold_rates")
            rate_count = cur.fetchone()[0]

        if rate_count == 0:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO gold_rates (rate_24k, rate_22k, rate_18k, updated_at)
                       VALUES (%s, %s, %s, CURRENT_TIMESTAMP)""",
                    (14296.00, 13101.00, 10728.00)
                )

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products")
            count = cur.fetchone()[0]

        if count == 0:
            sample = [
                ("Classic Solitaire Ring", "Rings", 45000, 4.2, "18K Gold", "Elegant everyday solitaire ring, hand-polished finish.", None, 1, 1),
                ("Bridal Kundan Necklace Set", "Necklaces", 128000, 38.5, "22K Gold", "Traditional Kundan necklace with matching earrings, ideal for weddings.", None, 1, 1),
                ("Gold Hoop Earrings", "Earrings", 18500, 6.1, "22K Gold", "Lightweight daily-wear hoops.", None, 1, 0),
                ("Classic Gold Bangles (Pair)", "Bangles & Bracelets", 92000, 24.0, "22K Gold", "Timeless plain gold bangles, sold as a pair.", None, 1, 0),
                ("Rope Chain 20 inch", "Chains", 61000, 15.3, "22K Gold", "Sturdy rope-design chain, unisex.", None, 1, 0),
            ]
            with conn.cursor() as cur:
                for row in sample:
                    cur.execute(
                        """INSERT INTO products
                           (name, category, price, weight_grams, purity, description, image_filename, in_stock, featured, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (*row, datetime.now().isoformat()),
                    )
        conn.close()
    except Exception as e:
        print(f"Database initialization warning/error: {e}")

CATEGORIES = ["Rings", "Necklaces", "Earrings", "Bangles & Bracelets", "Chains", "Other"]

# ---------------------------------------------------------------------------
# Real-Time Gold Rate & Dynamic Pricing Settings
# ---------------------------------------------------------------------------
PURITY_FACTORS = {
    "24K": 1.0,
    "22K": 22.0 / 24.0,
    "18K": 18.0 / 24.0,
    "14K": 14.0 / 24.0,
}

def update_live_gold_rates_if_needed(db):
    try:
        latest = db.execute("SELECT * FROM gold_rates ORDER BY updated_at DESC LIMIT 1").fetchone()
        if latest and latest["updated_at"]:
            last_updated = latest["updated_at"]
            if isinstance(last_updated, datetime) and (datetime.now() - last_updated) < timedelta(minutes=15):
                return

        api_key = os.environ.get("GOLD_API_KEY", "").strip()
        if api_key and api_key != "YOUR_API_KEY_HERE":
            url = "https://www.goldapi.io/api/XAU/INR"
            headers = {"x-access-token": api_key}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price_per_gram_24k = data.get("price_gram_24k")
                if not price_per_gram_24k and "price" in data:
                    price_per_gram_24k = float(data.get("price")) / 31.1034768
                
                if price_per_gram_24k:
                    indian_market_multiplier = 1.15 
                    rate_24k = float(price_per_gram_24k) * indian_market_multiplier
                    rate_22k = rate_24k * (22 / 24)
                    rate_18k = rate_24k * (18 / 24)
                                    
                    if latest:
                        db.execute(
                            """UPDATE gold_rates 
                               SET rate_24k = %s, rate_22k = %s, rate_18k = %s, updated_at = CURRENT_TIMESTAMP
                               WHERE id = %s""",
                            (rate_24k, rate_22k, rate_18k, latest["id"])
                        )
                    else:
                        db.execute(
                            """INSERT INTO gold_rates (rate_24k, rate_22k, rate_18k, updated_at)
                               VALUES (%s, %s, %s, CURRENT_TIMESTAMP)""",
                            (rate_24k, rate_22k, rate_18k)
                        )
                    db.commit()
    except Exception as e:
        print("Using cached/fallback rates due to API error:", e)

def get_live_gold_rate_per_gram():
    db = get_db()
    rates = db.execute("SELECT * FROM gold_rates ORDER BY updated_at DESC LIMIT 1").fetchone()
    if rates:
        update_time_str = rates["updated_at"].strftime("%H:%M:%S") if hasattr(rates["updated_at"], "strftime") else str(rates["updated_at"])[11:19]
        return float(rates["rate_24k"]), float(rates["rate_22k"]), float(rates["rate_18k"]), update_time_str
    return 14296.00, 13101.00, 10728.00, "00:00:00"

def calculate_dynamic_price(item, base_gold_rate_24k):
    try:
        weight = float(item.get("weight_grams") or 0.0)
    except (ValueError, TypeError):
        weight = 0.0

    purity = str(item.get("purity", "22K")).upper()
    
    factor = 1.0
    if "24K" in purity:
        factor = 1.0
    elif "22K" in purity:
        factor = 22 / 24
    elif "18K" in purity:
        factor = 18 / 24

    metal_cost = weight * float(base_gold_rate_24k) * factor
    making_charges = float(item.get("making_charges") or 0.0)
    stone_price = float(item.get("stone_price") or 0.0)
    
    total = metal_cost + making_charges + stone_price
    return round(total, 2)


def prepare_products(products_cursor_or_list):
    rate_24k, _, _, _ = get_live_gold_rate_per_gram()
    prepared = []
    for row in products_cursor_or_list:
        item = dict(row)
        item["calculated_price"] = calculate_dynamic_price(item, rate_24k)
        prepared.append(item)
    return prepared


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT_SECONDS = 8

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "jewellery123"))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/owner-access-portal-2026", methods=["GET", "POST"])
def owner_portal():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["logged_in"] = True
            flash("Welcome back, Owner!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect username or password.", "error")
    
    if session.get("logged_in"):
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_login.html")


def customer_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("customer_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def get_current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()


def get_cart_count():
    if "user_id" not in session:
        return 0
    db = get_db()
    row = db.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS n FROM cart_items WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()
    return row["n"] or 0


def get_ai_recommendations(db, interest_description, exclude_id=None, limit=4):
    catalog = db.execute(
        "SELECT id, name, category, price, purity FROM products WHERE in_stock = 1"
    ).fetchall()
    if not catalog:
        return []

    catalog = [c for c in catalog if c["id"] != exclude_id]
    if not catalog:
        return []

    catalog_text = "\n".join(
        f"id={c['id']} | {c['name']} | {c['category']} | ₹{c['price']} | {c['purity'] or ''}"
        for c in catalog
    )

    prompt = f"""You are a jewellery store recommendation engine.
Customer interest: {interest_description}

Available products:
{catalog_text}

Pick the {limit} product ids most likely to interest this customer.
Respond with ONLY a JSON array of integers, e.g. [3, 7, 12]. No other text."""

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        raw_text = resp.json().get("response", "").strip()
        start = raw_text.find("[")
        end = raw_text.rfind("]")
        if start == -1 or end == -1:
            return []
        ids = json.loads(raw_text[start:end + 1])
        ids = [int(i) for i in ids if isinstance(i, (int, float, str)) and str(i).strip().isdigit()]
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        return []

    if not ids:
        return []

    placeholders = ",".join(["?"] * len(ids))
    rows = db.execute(
        f"SELECT * FROM products WHERE id IN ({placeholders}) AND in_stock = 1", ids
    ).fetchall()
    
    rows_by_id = {r["id"]: r for r in rows}
    ordered = [rows_by_id[i] for i in ids if i in rows_by_id]
    return prepare_products(ordered[:limit])


FAQ_RULES = [
    (["hour", "open", "timing", "close"], "We're open daily from 10:00 AM to 8:30 PM."),
    (["custom", "bespoke", "design my own"], "Yes! We take custom and bridal orders — bring a reference image and we'll quote you a price and timeline. Visit our Contact page to get started."),
    (["return", "refund", "exchange"], "For returns, exchanges, or refunds, please call the store directly or visit us in person with your receipt — policies vary by item."),
    (["deliver", "shipping", "ship"], "We currently coordinate delivery by phone after you place an order — you'll be contacted to confirm details."),
    (["payment", "pay", "cod", "cash"], "We accept Pay at Store and Cash on Delivery right now. Online payment is coming soon."),
    (["purity", "karat", "22k", "18k", "hallmark"], "All our gold jewellery is hallmarked and clearly labeled with purity (typically 22K or 18K) on each product page."),
    (["contact", "phone", "call", "reach"], "You can reach us via the Contact page — leave your name and number and we'll call you back the same day."),
    (["price", "cost", "how much"], "Prices vary by piece and are shown on each product page — they include the current gold rate for that item's weight and purity."),
    (["location", "address", "where"], "Please check our Contact page for store address and directions."),
]


def get_faq_reply(message):
    text = message.lower()
    for keywords, reply in FAQ_RULES:
        if any(k in text for k in keywords):
            return reply
    return ("I'm not sure about that one — please try our Contact page to reach the store directly, or ask me about hours, pricing, purity, custom orders, payment, or delivery.")


@app.context_processor
def inject_globals():
    try:
        rate_24k, rate_22k, rate_18k, rate_time = get_live_gold_rate_per_gram()
    except Exception:
        rate_24k, rate_22k, rate_18k, rate_time = 14296.00, 13101.00, 10728.00, "00:00:00"
        
    return {
        "categories": CATEGORIES,
        "current_year": datetime.now().year,
        "current_user": get_current_user(),
        "cart_count": get_cart_count(),
        "live_gold_rate_24k": round(rate_24k, 2),
        "live_gold_rate_22k": round(rate_22k, 2),
        "live_gold_rate_18k": round(rate_18k, 2),
        "gold_rate_updated_at": rate_time,
    }


@app.before_request
def ensure_database_ready():
    """Lazily provisions tables if they haven't been created yet."""
    if not getattr(app, '_db_initialized', False):
        try:
            init_db()
            app._db_initialized = True
        except Exception as e:
            print(f"Skipping lazy DB init check: {e}")


@app.route("/")
@customer_login_required
def home():
    db = get_db()
    update_live_gold_rates_if_needed(db)
    return render_template("index.html")

@app.route("/catalog")
@customer_login_required
def catalog():
    db = get_db()
    update_live_gold_rates_if_needed(db)
    
    category = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest")

    sql = "SELECT * FROM products WHERE in_stock = 1"
    params = []

    if category and category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)

    if q:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    products = prepare_products(db.execute(sql, params).fetchall())

    if sort == "price_low":
        products.sort(key=lambda x: x["calculated_price"])
    elif sort == "price_high":
        products.sort(key=lambda x: x["calculated_price"], reverse=True)
    elif sort == "name":
        products.sort(key=lambda x: x["name"])
    else:
        products.sort(key=lambda x: x["created_at"], reverse=True)

    rate_24k, rate_22k, rate_18k, rate_time = get_live_gold_rate_per_gram()

    return render_template(
        "catalog.html", 
        products=products, 
        selected_category=category, 
        q=q, 
        sort=sort,
        categories=CATEGORIES,
        live_gold_rate_24k=round(rate_24k, 2),
        live_gold_rate_22k=round(rate_22k, 2),
        live_gold_rate_18k=round(rate_18k, 2),
        gold_rate_updated_at=rate_time
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    db = get_db()
    update_live_gold_rates_if_needed(db)
    
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)

    rate_24k, _, _, _ = get_live_gold_rate_per_gram()
    product = dict(product)
    product["calculated_price"] = calculate_dynamic_price(product, rate_24k)

    related = prepare_products(
        db.execute(
            "SELECT * FROM products WHERE category = ? AND id != ? AND in_stock = 1 LIMIT 4",
            (product["category"], product_id),
        ).fetchall()
    )
    ai_recommended = get_ai_recommendations(
        db,
        f"currently viewing '{product['name']}' ({product['category']}, ₹{product['calculated_price']}, {product['purity'] or 'unspecified purity'})",
        exclude_id=product_id,
    )
    return render_template(
        "product_detail.html", product=product, related=related, ai_recommended=ai_recommended
    )


@app.route("/product/<int:product_id>/enquire", methods=["POST"])
def enquire(product_id):
    db = get_db()
    name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not phone:
        flash("Please share your name and phone number so we can reach you back.", "error")
        return redirect(url_for("product_detail", product_id=product_id))

    db.execute(
        """INSERT INTO enquiries (product_id, customer_name, phone, message, created_at, handled)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (product_id, name, phone, message, datetime.now().isoformat()),
    )
    db.commit()
    flash("Thank you! We received your enquiry and will call you back shortly.", "success")
    return redirect(url_for("product_detail", product_id=product_id))


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        db = get_db()
        name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        message = request.form.get("message", "").strip()
        if not name or not phone:
            flash("Please share your name and phone number.", "error")
            return redirect(url_for("contact"))
        db.execute(
            """INSERT INTO enquiries (product_id, customer_name, phone, message, created_at, handled)
               VALUES (NULL, ?, ?, ?, ?, 0)""",
            (name, phone, message, datetime.now().isoformat()),
        )
        db.commit()
        flash("Thanks for reaching out. We'll get back to you soon.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")


@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return {"reply": "Ask me anything about hours, pricing, purity, custom orders, or delivery!"}
    return {"reply": get_faq_reply(message)}


@app.route("/register", methods=["GET", "POST"])
def register():
    return redirect(url_for("customer_login"))


@app.route("/login", methods=["GET", "POST"])
def customer_login():
    if session.get("user_id"):
        return redirect(url_for("catalog"))
        
    if request.method == "POST":
        db = get_db()
        name = request.form.get("customer_name", "").strip() or request.form.get("name", "").strip()
        phone = request.form.get("phone_number", "").strip() or request.form.get("phone", "").strip()

        # Fixed: Validate phone presence properly to prevent database UniqueViolation 500 crash
        if not phone:
            flash("Please enter a valid mobile number.", "error")
            return redirect(url_for("customer_login"))

        user = db.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()

        if user:
            update_name = name if name and name != user["name"] else user["name"]
            db.execute("UPDATE users SET name = ? WHERE id = ?", (update_name, user["id"]))
            db.commit()
            
            session["user_id"] = user["id"]
            flash(f"Welcome back, {update_name}!", "success")
        else:
            # If it's a new user, use the name they typed, or fallback cleanly
            if not name:
                name = f"Customer {phone[-4:]}"

            # Check if user already exists to avoid crashes
            existing_user = db.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
            
            if existing_user:
                session["user_id"] = existing_user["id"]
                flash(f"Welcome back, {existing_user['name']}!", "success")
            else:
                db.execute(
                    """INSERT INTO users (name, phone, email, address, password_hash, created_at)
                       VALUES (?, ?, NULL, '', NULL, ?)""",
                    (name, phone, datetime.now().isoformat()),
                )
                db.commit()
                new_user = db.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
                session["user_id"] = new_user["id"]
                flash(f"Welcome, {new_user['name']}! Your account has been created.", "success")

        next_url = request.args.get("next")
        if not next_url or "profile" in next_url or "login" in next_url:
            next_url = url_for("catalog")
            
        return redirect(next_url)

    return render_template("login.html")


@app.route("/logout")
def customer_logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
@customer_login_required
def profile():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        if not name or not phone:
            flash("Name and phone number are required.", "error")
        else:
            db.execute(
                "UPDATE users SET name = ?, phone = ?, address = ? WHERE id = ?",
                (name, phone, address, session["user_id"]),
            )
            db.commit()
            flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    user = get_current_user()
    return render_template("profile.html", user=user)


@app.route("/profile/delete", methods=["POST"])
@customer_login_required
def delete_profile():
    db = get_db()
    user_id = session["user_id"]
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    session.pop("user_id", None)
    flash("Your account and profile have been successfully removed.", "success")
    return redirect(url_for("home"))


@app.route("/wishlist")
@customer_login_required
def wishlist():
    db = get_db()
    items = prepare_products(
        db.execute(
            """SELECT products.* FROM wishlist_items
               JOIN products ON wishlist_items.product_id = products.id
               WHERE wishlist_items.user_id = ?
               ORDER BY wishlist_items.created_at DESC""",
            (session["user_id"],),
        ).fetchall()
    )
    return render_template("wishlist.html", products=items)


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
@customer_login_required
def wishlist_toggle(product_id):
    db = get_db()
    existing = db.execute(
        "SELECT id FROM wishlist_items WHERE user_id = ? AND product_id = ?",
        (session["user_id"], product_id),
    ).fetchone()
    if existing:
        db.execute("DELETE FROM wishlist_items WHERE id = ?", (existing["id"],))
        db.commit()
        flash("Removed from wishlist.", "success")
    else:
        db.execute(
            "INSERT INTO wishlist_items (user_id, product_id, created_at) VALUES (?, ?, ?)",
            (session["user_id"], product_id, datetime.now().isoformat()),
        )
        db.commit()
        flash("Added to wishlist.", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/cart")
@customer_login_required
def cart_view():
    db = get_db()
    items = db.execute(
        """SELECT cart_items.id AS cart_item_id, cart_items.quantity, products.*
           FROM cart_items JOIN products ON cart_items.product_id = products.id
           WHERE cart_items.user_id = ?
           ORDER BY cart_items.created_at DESC""",
        (session["user_id"],),
    ).fetchall()

    rate_24k, _, _, _ = get_live_gold_rate_per_gram()
    for item in items:
        item["calculated_price"] = calculate_dynamic_price(item, rate_24k)

    total = sum(i["calculated_price"] * i["quantity"] for i in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
@customer_login_required
def cart_add(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ? AND in_stock = 1", (product_id,)).fetchone()
    if product is None:
        flash("This item is not available.", "error")
        return redirect(request.referrer or url_for("catalog"))

    existing = db.execute(
        "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
        (session["user_id"], product_id),
    ).fetchone()
    if existing:
        db.execute("UPDATE cart_items SET quantity = quantity + 1 WHERE id = ?", (existing["id"],))
    else:
        db.execute(
            "INSERT INTO cart_items (user_id, product_id, quantity, created_at) VALUES (?, ?, 1, ?)",
            (session["user_id"], product_id, datetime.now().isoformat()),
        )
    db.commit()
    flash("Added to cart.", "success")
    return redirect(request.referrer or url_for("cart_view"))


@app.route("/cart/update/<int:cart_item_id>", methods=["POST"])
@customer_login_required
def cart_update(cart_item_id):
    db = get_db()
    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1
    quantity = max(1, min(quantity, 50))
    db.execute(
        "UPDATE cart_items SET quantity = ? WHERE id = ? AND user_id = ?",
        (quantity, cart_item_id, session["user_id"]),
    )
    db.commit()
    return redirect(url_for("cart_view"))


@app.route("/cart/remove/<int:cart_item_id>", methods=["POST"])
@customer_login_required
def cart_remove(cart_item_id):
    db = get_db()
    db.execute(
        "DELETE FROM cart_items WHERE id = ? AND user_id = ?", (cart_item_id, session["user_id"])
    )
    db.commit()
    flash("Removed from cart.", "success")
    return redirect(url_for("cart_view"))


@app.route("/checkout", methods=["GET", "POST"])
@customer_login_required
def checkout():
    db = get_db()
    items = db.execute(
        """SELECT cart_items.quantity, products.*
           FROM cart_items JOIN products ON cart_items.product_id = products.id
           WHERE cart_items.user_id = ?""",
        (session["user_id"],),
    ).fetchall()

    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart_view"))

    rate_24k, _, _, _ = get_live_gold_rate_per_gram()
    for item in items:
        item["calculated_price"] = calculate_dynamic_price(item, rate_24k)

    total = sum(i["calculated_price"] * i["quantity"] for i in items)

    if request.method == "POST":
        name = request.form.get("shipping_name", "").strip()
        phone = request.form.get("shipping_phone", "").strip()
        address = request.form.get("shipping_address", "").strip()
        payment_method = request.form.get("payment_method", "pay_at_store")

        if not name or not phone or not address:
            flash("Please fill in all shipping details.", "error")
            return redirect(url_for("checkout"))

        cur = db.execute(
            """INSERT INTO orders (user_id, total_amount, shipping_name, shipping_phone,
               shipping_address, payment_method, order_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'placed', ?) RETURNING id""",
            (session["user_id"], total, name, phone, address, payment_method,
             datetime.now().isoformat()),
        )
        order_row = cur.fetchone()
        order_id = order_row["id"]

        for item in items:
            db.execute(
                """INSERT INTO order_items (order_id, product_id, product_name, price, quantity)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, item["id"], item["name"], item["calculated_price"], item["quantity"]),
            )
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (session["user_id"],))
        db.commit()

        flash("Order placed! We'll contact you to confirm details.", "success")
        return redirect(url_for("order_detail", order_id=order_id))

    return render_template("checkout.html", items=items, total=total)


@app.route("/orders")
@customer_login_required
def orders():
    db = get_db()
    order_list = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)
    ).fetchall()
    return render_template("orders.html", orders=order_list)


@app.route("/orders/<int:order_id>")
@customer_login_required
def order_detail(order_id):
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"])
    ).fetchone()
    if order is None:
        abort(404)
    items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("order_detail.html", order=order, items=items)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["logged_in"] = True
            flash("Welcome back!", "success")
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        flash("Incorrect username or password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    total_products = db.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    in_stock = db.execute("SELECT COUNT(*) AS n FROM products WHERE in_stock = 1").fetchone()["n"]
    sold_out = total_products - in_stock
    new_enquiries = db.execute("SELECT COUNT(*) AS n FROM enquiries WHERE handled = 0").fetchone()["n"]
    stock_value = db.execute(
        "SELECT COALESCE(SUM(price), 0) AS total FROM products WHERE in_stock = 1"
    ).fetchone()["total"]
    recent_enquiries = db.execute(
        """SELECT enquiries.*, products.name AS product_name
           FROM enquiries LEFT JOIN products ON enquiries.product_id = products.id
           ORDER BY enquiries.created_at DESC LIMIT 8"""
    ).fetchall()

    total_orders = db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
    total_customers = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    total_revenue = db.execute(
        "SELECT COALESCE(SUM(total_amount), 0) AS total FROM orders WHERE order_status != 'cancelled'"
    ).fetchone()["total"]
    pending_orders = db.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE order_status = 'placed'"
    ).fetchone()["n"]
    recent_orders = db.execute(
        """SELECT orders.*, users.name AS customer_name
           FROM orders JOIN users ON orders.user_id = users.id
           ORDER BY orders.created_at DESC LIMIT 8"""
    ).fetchall()
    top_products = db.execute(
        """SELECT product_name, SUM(quantity) AS total_qty, SUM(price * quantity) AS total_sales
           FROM order_items GROUP BY product_name ORDER BY total_sales DESC LIMIT 5"""
    ).fetchall()

    return render_template(
        "admin_dashboard.html",
        total_products=total_products,
        in_stock=in_stock,
        sold_out=sold_out,
        new_enquiries=new_enquiries,
        stock_value=stock_value,
        recent_enquiries=recent_enquiries,
        total_orders=total_orders,
        total_customers=total_customers,
        total_revenue=total_revenue,
        pending_orders=pending_orders,
        recent_orders=recent_orders,
        top_products=top_products,
    )


ORDER_STATUSES = ["placed", "confirmed", "shipped", "delivered", "cancelled"]


@app.route("/admin/orders")
@login_required
def admin_orders():
    db = get_db()
    status_filter = request.args.get("status", "").strip()
    sql = """SELECT orders.*, users.name AS customer_name, users.phone AS customer_phone
              FROM orders JOIN users ON orders.user_id = users.id"""
    params = []
    if status_filter and status_filter in ORDER_STATUSES:
        sql += " WHERE orders.order_status = ?"
        params.append(status_filter)
    sql += " ORDER BY orders.created_at DESC"
    order_list = db.execute(sql, params).fetchall()
    return render_template(
        "admin_orders.html", orders=order_list, statuses=ORDER_STATUSES, status_filter=status_filter
    )


@app.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_detail(order_id):
    db = get_db()
    order = db.execute(
        """SELECT orders.*, users.name AS customer_name, users.email AS customer_email,
                  users.phone AS customer_phone
           FROM orders JOIN users ON orders.user_id = users.id WHERE orders.id = ?""",
        (order_id,),
    ).fetchone()
    if order is None:
        abort(404)
    items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return render_template(
        "admin_order_detail.html", order=order, items=items, statuses=ORDER_STATUSES
    )


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def admin_update_order_status(order_id):
    db = get_db()
    new_status = request.form.get("order_status", "")
    if new_status not in ORDER_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin_order_detail", order_id=order_id))
    db.execute("UPDATE orders SET order_status = ? WHERE id = ?", (new_status, order_id))
    db.commit()
    flash("Order status updated.", "success")
    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.route("/admin/customers")
@login_required
def admin_customers():
    db = get_db()
    q = request.args.get("q", "").strip()
    sql = """SELECT users.*,
                    (SELECT COUNT(*) FROM orders WHERE orders.user_id = users.id) AS order_count,
                    (SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE orders.user_id = users.id
                     AND orders.order_status != 'cancelled') AS total_spent
             FROM users"""
    params = []
    if q:
        sql += " WHERE users.name LIKE ? OR users.email LIKE ? OR users.phone LIKE ?"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY users.created_at DESC"
    customers = db.execute(sql, params).fetchall()
    return render_template("admin_customers.html", customers=customers, q=q)


@app.route("/admin/customers/<int:user_id>")
@login_required
def admin_customer_detail(user_id):
    db = get_db()
    customer = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if customer is None:
        abort(404)
    customer_orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    return render_template(
        "admin_customer_detail.html", customer=customer, orders=customer_orders
    )


@app.route("/admin/products")
@login_required
def admin_products():
    db = get_db()
    products = prepare_products(
        db.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    )
    return render_template("admin_products.html", products=products)


@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
def admin_add_product():
    if request.method == "POST":
        return save_product()
    return render_template("admin_product_form.html", product=None)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)
    if request.method == "POST":
        return save_product(product_id=product_id, existing_image=product["image_filename"])
    return render_template("admin_product_form.html", product=product)


def save_product(product_id=None, existing_image=None):
    db = get_db()
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "0").strip()
    weight = request.form.get("weight_grams", "").strip()
    purity = request.form.get("purity", "").strip()
    description = request.form.get("description", "").strip()
    in_stock = 1 if request.form.get("in_stock") == "on" else 0
    featured = 1 if request.form.get("featured") == "on" else 0

    if not name or not category:
        flash("Name and category are required.", "error")
        return redirect(url_for("admin_products"))

    try:
        price = float(price)
    except ValueError:
        price = 0.0
    weight = float(weight) if weight else None

    image_filename = existing_image
    file = request.files.get("image")
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        image_filename = filename

    if product_id:
        db.execute(
            """UPDATE products SET name=?, category=?, price=?, weight_grams=?, purity=?,
               description=?, image_filename=?, in_stock=?, featured=? WHERE id=?""",
            (name, category, price, weight, purity, description, image_filename,
             in_stock, featured, product_id),
        )
        flash("Product updated.", "success")
    else:
        db.execute(
            """INSERT INTO products
               (name, category, price, weight_grams, purity, description, image_filename,
                in_stock, featured, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, price, weight, purity, description, image_filename,
               in_stock, featured, datetime.now().isoformat()),
        )
        flash("Product added.", "success")
    db.commit()
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/toggle-stock", methods=["POST"])
@login_required
def admin_toggle_stock(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)
    new_status = 0 if product["in_stock"] else 1
    db.execute("UPDATE products SET in_stock = ? WHERE id = ?", (new_status, product_id))
    db.commit()
    flash("Stock status updated.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
def admin_delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/enquiries")
@login_required
def admin_enquiries():
    db = get_db()
    enquiries = db.execute(
        """SELECT enquiries.*, products.name AS product_name
           FROM enquiries LEFT JOIN products ON enquiries.product_id = products.id
           ORDER BY enquiries.created_at DESC"""
    ).fetchall()
    return render_template("admin_enquiries.html", enquiries=enquiries)


@app.route("/admin/enquiries/<int:enquiry_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_enquiry(enquiry_id):
    db = get_db()
    enquiry = db.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
    if enquiry is None:
        abort(404)
    new_status = 0 if enquiry["handled"] else 1
    db.execute("UPDATE enquiries SET handled = ? WHERE id = ?", (new_status, enquiry_id))
    db.commit()
    return redirect(url_for("admin_enquiries"))


if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(
        debug=debug_mode,
        host=os.environ.get("FLASK_HOST", "127.0.0.1" if debug_mode else "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
    )
