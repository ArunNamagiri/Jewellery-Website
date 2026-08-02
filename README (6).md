# AI Jewellery Store — Daily Business Website

A complete, ready-to-run website for a jewellery shop:

- **Customers** can browse the catalog, create an account, save items to
  a wishlist, add to cart, check out, and view their order history.
- **The shop owner** gets a password-protected panel to manage products,
  process orders, view customers, and see enquiries.
- A **rule-based FAQ chatbot** answers common questions (hours, pricing,
  purity, custom orders) with no external API or cost.
- **Optional AI product recommendations** via a locally-running Ollama
  model (no API key needed) — the site works perfectly without this if
  you don't set it up.

## 1. First-time setup (do this once)

This version uses **MySQL** for storage instead of a single file, so you
need a MySQL server running first.

### Step A — Install MySQL

The easiest route on Windows is **XAMPP** (https://www.apachefriends.org) —
install it, then open the XAMPP Control Panel and click **Start** next to
MySQL. That's your database server running.

(Already have MySQL Workbench, WAMP, or a MySQL server elsewhere? Any of
those work too — you just need the host, username, and password.)

### Step B — Create a database and user

Open phpMyAdmin (XAMPP Control Panel → MySQL → Admin) or run this in the
MySQL command line:

```sql
CREATE DATABASE jewellery_store CHARACTER SET utf8mb4;
CREATE USER 'jewellery_user'@'localhost' IDENTIFIED BY 'jewellery_pass';
GRANT ALL PRIVILEGES ON jewellery_store.* TO 'jewellery_user'@'localhost';
FLUSH PRIVILEGES;
```

(Feel free to pick your own username/password — just also update `app.py`,
see Step C.)

### Step C — Point the app at your database

Open `app.py` and check these lines near the top match what you created:

```python
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "jewellery_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "jewellery_pass")
DB_NAME = os.environ.get("DB_NAME", "jewellery_store")
```

If you used XAMPP's default MySQL root account with no password instead,
set `DB_USER = "root"` and `DB_PASSWORD = ""`.

### Step D — Install Python packages and run

```
python -m pip install -r requirements.txt
python app.py
```

The first time it runs, it automatically creates the `products` and
`enquiries` tables inside `jewellery_store` and adds 5 sample products,
so you have something to look at immediately. Every time after that, it
just connects to the same database — nothing is recreated or wiped.

Now open your browser to:

- **Customer site:** http://127.0.0.1:5000
- **Shop owner panel:** http://127.0.0.1:5000/admin
  - Username: `admin`
  - Password: `jewellery123`

## 2. Using it every day

1. Open a terminal, go to this folder, run `python app.py`, and leave
   that window open — it's your web server.
2. Go to `http://127.0.0.1:5000/admin` and log in.
3. Use **Manage Products** to:
   - **Add Product** — upload a photo, set name, category, price,
     weight, purity, and description.
   - **Mark Sold / Mark In Stock** — one click, no need to delete
     anything.
   - **Edit** — update the price any time gold rates change.
4. Check **Customer Enquiries** to see who asked about which piece and
   their phone number, so you can call them back.
5. When you're done for the day, close the terminal window (or leave it
   running if the computer stays on).

Everything is saved in `database/store.db` automatically — closing the
program never loses your data.

## 3. Before you show this to real customers

- **Change the admin password.** Open `app.py`, find this line near the
  top:
  ```python
  ADMIN_PASSWORD_HASH = generate_password_hash("jewellery123")
  ```
  Replace `"jewellery123"` with your own password.
- **Change the secret key.** Also near the top of `app.py`:
  ```python
  app.config["SECRET_KEY"] = "change-this-secret-key-before-going-live"
  ```
  Replace with any random text.
- **Turn off debug mode** for daily/public use. At the very bottom of
  `app.py`, change:
  ```python
  app.run(debug=True)
  ```
  to
  ```python
  app.run(debug=False, host="0.0.0.0", port=5000)
  ```
  `host="0.0.0.0"` lets other devices on the same shop Wi-Fi (a tablet at
  the counter, for example) open the site too, using your computer's
  local IP address.

## 4. Running with Docker (optional, no manual MySQL install needed)

If you have Docker Desktop installed, this spins up the app **and** MySQL
together, so you can skip sections 1–3 entirely.

```
cp .env.example .env
```

Open `.env` and set `SECRET_KEY`, `ADMIN_PASSWORD`, and `MYSQL_ROOT_PASSWORD`
to your own values (don't leave the placeholders in place for real use).

Then:

```
docker compose up --build
```

- First run creates the MySQL container, waits for it to become healthy,
  then starts the Flask app and creates tables automatically.
- Site: http://localhost:5000
- Admin panel: http://localhost:5000/admin (uses `ADMIN_USERNAME` /
  `ADMIN_PASSWORD` from your `.env`)
- Product photos persist in a Docker volume across restarts.
- To stop: `Ctrl+C`, then `docker compose down` (add `-v` to also wipe the
  database volume and start completely fresh).

**AI recommendations in Docker**: if you have Ollama running on your host
machine (not in Docker), the app reaches it via `host.docker.internal`
automatically — no extra config needed. If Ollama isn't running, that
section of the site just doesn't appear; nothing breaks.

*Note: this Dockerfile/compose setup hasn't been build-tested against a
live Docker daemon in this environment — please run `docker compose up
--build` yourself and check the logs on first run before relying on it.*

## 5. Putting it online (optional)

Right now this runs on one computer only. If you want customers to
browse it from their own phones over the internet (not just in-shop),
the simplest options are:
- **PythonAnywhere** or **Render** — free/cheap hosting made for small
  Flask apps like this one, no server management needed.
- Ask a developer to point a domain name (e.g. `yourshopname.com`) at
  the hosted version.

## 6. Folder guide

```
AI-Jewellery-Store/
├── app.py                 # All the website logic + MySQL connection settings
├── requirements.txt       # Python packages needed (Flask, PyMySQL, requests)
├── Dockerfile              # Container build for the Flask app
├── docker-compose.yml      # Flask + MySQL, one command to run both
├── entrypoint.sh           # Docker startup: create tables, then start gunicorn
├── .env.example             # Template for environment variables (copy to .env)
├── templates/              # All page designs (HTML) — customer + admin
├── static/css/style.css    # Visual design
├── static/js/script.js     # Interactive bits (menu, alerts, chat widget)
└── static/uploads/         # Product photos you upload get saved here
```

Your product and enquiry data now lives inside the `jewellery_store`
MySQL database (viewable any time in phpMyAdmin or MySQL Workbench),
not in a file in this folder.

## 7. Common questions

**"pip is not recognized" / "pip: command not found"**
Use `python -m pip install -r requirements.txt` instead of `pip install ...`.

**`pymysql.err.OperationalError: (2003, "Can't connect to MySQL server...")`**
Your MySQL server isn't running. Open XAMPP Control Panel and click
**Start** next to MySQL, then try again.

**`Access denied for user 'jewellery_user'@'localhost'`**
The username/password in `app.py` doesn't match what you created in
Step B. Double check both, or re-run the `CREATE USER` command.

**I want to reset all the sample data.**
In phpMyAdmin (or via the MySQL command line), run
`DROP DATABASE jewellery_store;` then run `python app.py` again — a
fresh database with sample products will be created automatically.

**Can two people use the admin panel at once?**
Yes — that's one advantage of MySQL over the old single-file version.
As long as both computers can reach the MySQL server (same Wi-Fi, or the
server is on a shared machine) and the Flask app is started with
`host="0.0.0.0"` as shown above, a tablet at the counter and your laptop
can both add/edit products safely at the same time.

**Can I see my data outside the website, e.g. in a spreadsheet?**
Yes — open phpMyAdmin, click the `jewellery_store` database, then the
`products` or `enquiries` table, and use **Export** to save as CSV or
Excel.
