"""Live XAU/INR gold-rate adapter for the Flask jewellery store."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

import app as core

RATE_REFRESH_SECONDS = int(os.environ.get("GOLD_RATE_REFRESH_SECONDS", "300"))
GOLD_API_KEY = os.environ.get("GOLD_API_KEY", "").strip()
GOLD_API_URL = "https://www.goldapi.io/api/XAU/INR"
IST = ZoneInfo("Asia/Kolkata")


def _format_time(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(IST).strftime("%H:%M:%S")
    return datetime.now(IST).strftime("%H:%M:%S")


def _db_rates():
    db = core.get_db()
    return db.execute("SELECT * FROM gold_rates ORDER BY updated_at DESC LIMIT 1").fetchone()


def _save_rates(rate_24k, rate_22k, rate_18k):
    db = core.get_db()
    row = _db_rates()
    if row:
        db.execute(
            """UPDATE gold_rates
               SET rate_24k = ?, rate_22k = ?, rate_18k = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (rate_24k, rate_22k, rate_18k, row["id"]),
        )
    else:
        db.execute(
            """INSERT INTO gold_rates (rate_24k, rate_22k, rate_18k, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (rate_24k, rate_22k, rate_18k),
        )
    db.commit()
    return _db_rates()


def refresh_live_rates(force=False):
    row = _db_rates()
    now = datetime.now(timezone.utc)

    if row and not force:
        updated = row["updated_at"]
        if isinstance(updated, datetime):
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if (now - updated).total_seconds() < RATE_REFRESH_SECONDS:
                return row, False

    if not GOLD_API_KEY:
        return row, False

    try:
        response = requests.get(
            GOLD_API_URL,
            headers={"x-access-token": GOLD_API_KEY, "Content-Type": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()

        rate_24k = data.get("price_gram_24k")
        rate_22k = data.get("price_gram_22k")
        rate_18k = data.get("price_gram_18k")
        if rate_24k is None:
            raise ValueError("Gold API did not return price_gram_24k")

        rate_24k = float(rate_24k)
        rate_22k = float(rate_22k if rate_22k is not None else rate_24k * 22 / 24)
        rate_18k = float(rate_18k if rate_18k is not None else rate_24k * 18 / 24)
        return _save_rates(rate_24k, rate_22k, rate_18k), True
    except Exception as exc:
        print(f"Live gold-rate update failed; using cached rate: {exc}")
        return row, False


def live_gold_rate_per_gram():
    row, _ = refresh_live_rates()
    if row:
        return (
            float(row["rate_24k"]),
            float(row["rate_22k"]),
            float(row["rate_18k"]),
            _format_time(row["updated_at"]),
        )
    return 14296.00, 13101.00, 10728.00, datetime.now(IST).strftime("%H:%M:%S")


def live_refresh_endpoint():
    row, refreshed = refresh_live_rates(force=True)
    if row:
        return core.jsonify({
            "rate_24k": float(row["rate_24k"]),
            "rate_22k": float(row["rate_22k"]),
            "rate_18k": float(row["rate_18k"]),
            "synced_at": _format_time(row["updated_at"]),
            "next_refresh_seconds": RATE_REFRESH_SECONDS,
            "source": "GoldAPI.io" if GOLD_API_KEY else "Database cache",
            "refreshed": refreshed,
        })
    return core.jsonify({
        "rate_24k": 14296.00,
        "rate_22k": 13101.00,
        "rate_18k": 10728.00,
        "synced_at": datetime.now(IST).strftime("%H:%M:%S"),
        "next_refresh_seconds": RATE_REFRESH_SECONDS,
        "source": "Fallback",
        "refreshed": False,
    })


# Override the old hard-coded updater/endpoint before Gunicorn starts serving.
core.update_live_gold_rates_if_needed = lambda db: refresh_live_rates()[0]
core.get_live_gold_rate_per_gram = live_gold_rate_per_gram
core.app.view_functions["refresh_gold_rates"] = live_refresh_endpoint

app = core.app
