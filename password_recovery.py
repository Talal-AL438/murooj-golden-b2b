import hashlib
import secrets
from datetime import datetime, timedelta

from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash

from database_adapter import connect_db

TOKEN_MINUTES = 30


def _now():
    return datetime.utcnow()


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ensure_table():
    conn = connect_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens(user_id)")
        conn.commit()
    finally:
        conn.close()


def register_password_recovery(app):
    """Register privacy-preserving, expiring, one-time password recovery."""
    _ensure_table()

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        lang = session.get("lang", "ar")
        messages = {
            "ar": "إذا كان البريد مسجلاً لدينا، فسيتم إرسال رابط إعادة تعيين آمن إليه.",
            "en": "If the email is registered, a secure password reset link will be sent to it.",
            "id": "Jika email terdaftar, tautan reset kata sandi yang aman akan dikirim.",
            "ms": "Jika e-mel didaftarkan, pautan tetapan semula kata laluan yang selamat akan dihantar.",
        }
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            conn = connect_db()
            try:
                user = conn.execute("SELECT id, email, active FROM users WHERE email=%s", (email,)).fetchone()
                if user and user["active"]:
                    # Invalidate previous unused reset links for this account.
                    conn.execute(
                        "UPDATE password_reset_tokens SET used_at=%s WHERE user_id=%s AND used_at IS NULL",
                        (_now(), user["id"]),
                    )
                    token = secrets.token_urlsafe(32)
                    conn.execute(
                        "INSERT INTO password_reset_tokens(user_id, token_hash, expires_at) VALUES(%s,%s,%s)",
                        (user["id"], _token_hash(token), _now() + timedelta(minutes=TOKEN_MINUTES)),
                    )
                    conn.commit()
                    # Email delivery is wired in the next step. Never log the raw token.
                    session["password_reset_email_pending"] = user["email"]
                    session["password_reset_token_pending"] = token
            finally:
                conn.close()
            flash(messages.get(lang, messages["ar"]))
            return redirect(url_for("login"))
        return render_template("forgot_password.html", user=None)

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        lang = session.get("lang", "ar")
        invalid = {
            "ar": "رابط إعادة التعيين غير صالح أو انتهت مدته. اطلب رابطاً جديداً.",
            "en": "This reset link is invalid or expired. Please request a new one.",
            "id": "Tautan reset tidak valid atau kedaluwarsa. Silakan minta tautan baru.",
            "ms": "Pautan tetapan semula tidak sah atau telah tamat tempoh. Sila minta pautan baharu.",
        }
        mismatch = {
            "ar": "كلمتا المرور غير متطابقتين.", "en": "Passwords do not match.",
            "id": "Kata sandi tidak cocok.", "ms": "Kata laluan tidak sepadan.",
        }
        success = {
            "ar": "تم تغيير كلمة المرور بنجاح. يمكنك تسجيل الدخول الآن.",
            "en": "Password changed successfully. You can now log in.",
            "id": "Kata sandi berhasil diubah. Anda sekarang dapat masuk.",
            "ms": "Kata laluan berjaya ditukar. Anda kini boleh log masuk.",
        }
        conn = connect_db()
        try:
            row = conn.execute(
                "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token_hash=%s",
                (_token_hash(token),),
            ).fetchone()
            if not row or row["used_at"] is not None or row["expires_at"] <= _now():
                flash(invalid.get(lang, invalid["ar"]))
                return redirect(url_for("forgot_password"))

            if request.method == "POST":
                password = request.form.get("password", "")
                confirm = request.form.get("confirm_password", "")
                if len(password) < 8:
                    flash(invalid.get(lang, invalid["ar"]))
                    return render_template("reset_password.html", user=None)
                if password != confirm:
                    flash(mismatch.get(lang, mismatch["ar"]))
                    return render_template("reset_password.html", user=None)
                conn.execute(
                    "UPDATE users SET password_hash=%s WHERE id=%s",
                    (generate_password_hash(password), row["user_id"]),
                )
                conn.execute(
                    "UPDATE password_reset_tokens SET used_at=%s WHERE id=%s",
                    (_now(), row["id"]),
                )
                conn.commit()
                session.pop("user_id", None)
                flash(success.get(lang, success["ar"]))
                return redirect(url_for("login"))
            return render_template("reset_password.html", user=None)
        finally:
            conn.close()
