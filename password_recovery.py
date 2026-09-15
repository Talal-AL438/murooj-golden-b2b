from flask import render_template, request, redirect, url_for, session, flash


def register_password_recovery(app):
    """Register a privacy-preserving password recovery request page."""

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        lang = session.get("lang", "ar")
        messages = {
            "ar": "إذا كان البريد مسجلاً لدينا، فسيتم التعامل مع طلب إعادة التعيين بعد التحقق من الحساب. تواصل مع إدارة مروج الذهبية عبر WhatsApp.",
            "en": "If the email is registered, the reset request will be handled after account verification. Contact Murooj Golden administration via WhatsApp.",
            "id": "Jika email terdaftar, permintaan reset akan diproses setelah verifikasi akun. Hubungi administrasi Murooj Golden melalui WhatsApp.",
            "ms": "Jika e-mel didaftarkan, permintaan tetapan semula akan diproses selepas pengesahan akaun. Hubungi pentadbiran Murooj Golden melalui WhatsApp.",
        }
        if request.method == "POST":
            # Deliberately return the same response whether or not an account exists.
            # This prevents exposing which email addresses are registered.
            flash(messages.get(lang, messages["ar"]))
            return redirect(url_for("login"))
        return render_template("forgot_password.html", user=None)
