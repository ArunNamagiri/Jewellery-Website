import base64
import io
import os
import time

import pyotp
import qrcode
from flask import redirect, request, render_template, session, url_for, flash

from app import app, get_connection

OTP_ISSUER = os.environ.get("OTP_ISSUER", "AI Jewellery Store")
OTP_ACCOUNT = os.environ.get("OTP_ACCOUNT", os.environ.get("ADMIN_USERNAME", "admin"))


def otp_db_setup():
    conn = get_connection()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_totp (
                    id SMALLINT PRIMARY KEY DEFAULT 1,
                    secret VARCHAR(64) NOT NULL,
                    enabled SMALLINT NOT NULL DEFAULT 0,
                    last_counter BIGINT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("SELECT id, secret, enabled, last_counter FROM admin_totp WHERE id = 1")
            row = cur.fetchone()
            if not row:
                secret = pyotp.random_base32()
                cur.execute(
                    "INSERT INTO admin_totp (id, secret, enabled) VALUES (1, %s, 0)",
                    (secret,),
                )
    finally:
        conn.close()


def get_otp_record():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, secret, enabled, last_counter FROM admin_totp WHERE id = 1")
            return cur.fetchone()
    finally:
        conn.close()


def set_otp_state(enabled=None, last_counter=None):
    conn = get_connection()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            if enabled is not None and last_counter is not None:
                cur.execute(
                    "UPDATE admin_totp SET enabled=%s, last_counter=%s WHERE id=1",
                    (int(enabled), last_counter),
                )
            elif enabled is not None:
                cur.execute("UPDATE admin_totp SET enabled=%s WHERE id=1", (int(enabled),))
            else:
                cur.execute("UPDATE admin_totp SET last_counter=%s WHERE id=1", (last_counter,))
    finally:
        conn.close()


def verify_code(code):
    record = get_otp_record()
    if not record:
        return False

    code = str(code).strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return False

    secret = record[1]
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return False

    now = int(time.time())
    matched_counter = None
    current_counter = now // totp.interval
    for offset in (-1, 0, 1):
        counter = current_counter + offset
        if totp.at(counter * totp.interval) == code:
            matched_counter = counter
            break

    if matched_counter is None:
        return False

    last_counter = record[3]
    if last_counter is not None and matched_counter <= int(last_counter):
        return False

    set_otp_state(last_counter=matched_counter)
    return True


def otp_uri():
    record = get_otp_record()
    secret = record[1]
    return pyotp.TOTP(secret).provisioning_uri(
        name=OTP_ACCOUNT,
        issuer_name=OTP_ISSUER,
    )


def qr_data_uri(uri):
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    image = qr.make_image()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _pending_redirect(response):
    if request.endpoint in {"admin_login", "owner_portal"} and session.get("logged_in"):
        record = get_otp_record()
        session["logged_in"] = False
        session["otp_verified"] = False
        session["otp_pending"] = True
        target = "otp_setup" if not record[2] else "otp_verify"
        next_url = request.args.get("next") or url_for("admin_dashboard")
        response.status_code = 302
        response.headers["Location"] = url_for(target, next=next_url)
    return response


@app.after_request
def otp_after_request(response):
    return _pending_redirect(response)


@app.before_request
def otp_guard():
    endpoint = request.endpoint or ""
    if endpoint in {"otp_setup", "otp_verify", "admin_login", "owner_portal", "static"}:
        return None

    protected = endpoint.startswith("admin_") or request.path.startswith("/admin/")
    if not protected:
        return None

    if not session.get("logged_in") or not session.get("otp_verified"):
        if session.get("otp_pending") or session.get("logged_in"):
            record = get_otp_record()
            return redirect(url_for("otp_setup" if not record[2] else "otp_verify"))
        return redirect(url_for("admin_login", next=request.path))
    return None


@app.route("/admin/otp/setup", methods=["GET", "POST"])
def otp_setup():
    record = get_otp_record()
    if record and record[2]:
        return redirect(url_for("otp_verify"))

    if request.method == "POST":
        code = request.form.get("code", "").strip().replace(" ", "")
        if verify_code(code):
            set_otp_state(enabled=1)
            session["otp_verified"] = True
            session["otp_pending"] = False
            session["logged_in"] = True
            flash("Authenticator setup complete. Future logins will only ask for the 6-digit code.", "success")
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Invalid or expired authenticator code. Enter the current 6-digit code.", "error")

    return render_template(
        "admin_otp_setup.html",
        qr_code=qr_data_uri(otp_uri()),
        secret=record[1],
    )


@app.route("/admin/otp", methods=["GET", "POST"])
def otp_verify():
    record = get_otp_record()
    if not record or not record[2]:
        return redirect(url_for("otp_setup"))

    if request.method == "POST":
        code = request.form.get("code", "").strip().replace(" ", "")
        if verify_code(code):
            session["otp_verified"] = True
            session["otp_pending"] = False
            session["logged_in"] = True
            flash("Two-factor authentication successful.", "success")
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Invalid or expired code. Enter the current 6-digit code from Google Authenticator.", "error")

    return render_template("admin_otp.html")


otp_db_setup()
