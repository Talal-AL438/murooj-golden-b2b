import hashlib
import secrets
from datetime import datetime, timedelta
from flask import request, render_template, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash


def register_password_recovery(app, db):
    def ensure_table(c):
        c.execute("CREATE TABLE IF NOT EXISTS password_reset_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT UNIQUE NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id))")

    def text(key):
        lang=session.get('lang','ar')
        messages={
            'requested':{
                'ar':'إذا كان البريد مسجلاً لدينا، تم إنشاء طلب استعادة آمن. أثناء النسخة التجريبية لن يُرسل البريد حتى يتم تفعيل خدمة الإرسال.',
                'en':'If the email is registered, a secure recovery request has been created. During the trial, email delivery stays disabled until the mail service is activated.',
                'id':'Jika email terdaftar, permintaan pemulihan aman telah dibuat. Selama masa uji coba, pengiriman email tetap dinonaktifkan sampai layanan email diaktifkan.',
                'ms':'Jika e-mel didaftarkan, permintaan pemulihan selamat telah dibuat. Semasa tempoh percubaan, penghantaran e-mel kekal dilumpuhkan sehingga perkhidmatan e-mel diaktifkan.'},
            'invalid':{'ar':'رابط الاستعادة غير صالح أو انتهت صلاحيته.','en':'The recovery link is invalid or has expired.','id':'Tautan pemulihan tidak valid atau telah kedaluwarsa.','ms':'Pautan pemulihan tidak sah atau telah tamat tempoh.'},
            'short':{'ar':'يجب أن تكون كلمة المرور 8 أحرف على الأقل.','en':'Password must be at least 8 characters.','id':'Kata sandi minimal 8 karakter.','ms':'Kata laluan mestilah sekurang-kurangnya 8 aksara.'},
            'mismatch':{'ar':'كلمتا المرور غير متطابقتين.','en':'Passwords do not match.','id':'Kata sandi tidak cocok.','ms':'Kata laluan tidak sepadan.'},
            'done':{'ar':'تم تغيير كلمة المرور بنجاح. يمكنك تسجيل الدخول الآن.','en':'Password changed successfully. You can log in now.','id':'Kata sandi berhasil diubah. Anda sekarang dapat masuk.','ms':'Kata laluan berjaya diubah. Anda boleh log masuk sekarang.'}}
        return messages[key].get(lang,messages[key]['ar'])

    @app.route('/forgot-password',methods=['GET','POST'])
    def forgot_password():
        if request.method=='POST':
            email=request.form.get('email','').strip().lower()
            c=db();ensure_table(c)
            user=c.execute("SELECT id FROM users WHERE lower(email)=? AND active=1",(email,)).fetchone()
            if user:
                raw=secrets.token_urlsafe(32);token_hash=hashlib.sha256(raw.encode()).hexdigest();now=datetime.utcnow();expires=now+timedelta(minutes=30)
                c.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",(now.isoformat(),user['id']))
                c.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)",(user['id'],token_hash,expires.isoformat(),now.isoformat()))
                # Never store the raw token. Email delivery will use `raw` only after the trial mail service is configured.
            c.commit();c.close();flash(text('requested'));return redirect(url_for('login'))
        return render_template('forgot_password.html')

    @app.route('/reset-password/<token>',methods=['GET','POST'])
    def reset_password(token):
        token_hash=hashlib.sha256(token.encode()).hexdigest();c=db();ensure_table(c)
        row=c.execute("SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL",(token_hash,)).fetchone()
        valid=False
        if row:
            try:valid=datetime.fromisoformat(row['expires_at'])>datetime.utcnow()
            except (TypeError,ValueError):valid=False
        if not valid:
            c.close();flash(text('invalid'));return redirect(url_for('forgot_password'))
        if request.method=='POST':
            password=request.form.get('password','');confirm=request.form.get('confirm_password','')
            if len(password)<8:c.close();flash(text('short'));return render_template('reset_password.html')
            if password!=confirm:c.close();flash(text('mismatch'));return render_template('reset_password.html')
            now=datetime.utcnow().isoformat();c.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(password),row['user_id']));c.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",(now,row['user_id']));c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(row['user_id'],'password_reset','password reset completed',now));c.commit();c.close();session.pop('uid',None);flash(text('done'));return redirect(url_for('login'))
        c.close();return render_template('reset_password.html')
