import hashlib
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from flask import request, render_template, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash


def register_password_recovery(app, db):
    def ensure_table(c):
        c.execute("CREATE TABLE IF NOT EXISTS password_reset_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT UNIQUE NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id))")

    def setting(c, key, default=''):
        row=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return row['value'] if row and row['value'] is not None else default

    def send_reset_email(c, recipient, reset_url):
        """Send through Resend when configured. No API key or raw token is stored in the database."""
        api_key=os.environ.get('RESEND_API_KEY','').strip()
        sender=os.environ.get('RESEND_FROM_EMAIL','').strip()
        sender_name=os.environ.get('RESEND_FROM_NAME','MUROOJ GOLDEN').strip() or 'MUROOJ GOLDEN'
        reply_to=setting(c,'email','').strip()
        if not api_key or not sender:
            return False
        payload={
            'from':f'{sender_name} <{sender}>',
            'to':[recipient],
            'subject':'MUROOJ GOLDEN — Password Reset',
            'text':f'Use this secure link to reset your MUROOJ GOLDEN B2B password. The link expires in 30 minutes:\n\n{reset_url}\n\nIf you did not request this, ignore this email.',
            'html':f'''<!doctype html><html><body style="font-family:Arial,sans-serif;background:#f6f4ef;padding:24px"><table role="presentation" width="100%"><tr><td align="center"><table role="presentation" width="560" style="max-width:560px;background:#fff;padding:28px;border-radius:12px"><tr><td><h2>MUROOJ GOLDEN B2B</h2><p>A password reset was requested for your account.</p><p><a href="{reset_url}" style="display:inline-block;padding:12px 20px;background:#111;color:#d8b35a;text-decoration:none;border-radius:8px">Reset password</a></p><p>This secure link expires in 30 minutes. If you did not request it, ignore this email.</p></td></tr></table></td></tr></table></body></html>'''
        }
        if reply_to:
            payload['reply_to']=reply_to
        req=urllib.request.Request('https://api.resend.com/emails',data=json.dumps(payload).encode('utf-8'),headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=10) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return False

    def text(key):
        lang=session.get('lang','ar')
        messages={
            'requested':{
                'ar':'إذا كان البريد مسجلاً لدينا، فسيصلك رابط استعادة آمن عند تفعيل خدمة البريد.',
                'en':'If the email is registered, a secure recovery link will be sent when email delivery is enabled.',
                'id':'Jika email terdaftar, tautan pemulihan aman akan dikirim saat layanan email diaktifkan.',
                'ms':'Jika e-mel didaftarkan, pautan pemulihan selamat akan dihantar apabila perkhidmatan e-mel diaktifkan.'},
            'invalid':{'ar':'رابط الاستعادة غير صالح أو انتهت صلاحيته.','en':'The recovery link is invalid or has expired.','id':'Tautan pemulihan tidak valid atau telah kedaluwarsa.','ms':'Pautan pemulihan tidak sah atau telah tamat tempoh.'},
            'short':{'ar':'يجب أن تكون كلمة المرور 8 أحرف على الأقل.','en':'Password must be at least 8 characters.','id':'Kata sandi minimal 8 karakter.','ms':'Kata laluan mestilah sekurang-kurangnya 8 aksara.'},
            'mismatch':{'ar':'كلمتا المرور غير متطابقتين.','en':'Passwords do not match.','id':'Kata sandi tidak cocok.','ms':'Kata laluan tidak sepadan.'},
            'same':{'ar':'اختر كلمة مرور جديدة مختلفة عن كلمة المرور الحالية.','en':'Choose a new password different from your current password.','id':'Pilih kata sandi baru yang berbeda dari kata sandi saat ini.','ms':'Pilih kata laluan baharu yang berbeza daripada kata laluan semasa.'},
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
                c.commit()
                reset_url=url_for('reset_password',token=raw,_external=True)
                sent=send_reset_email(c,email,reset_url)
                c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(user['id'],'password_reset_requested','email delivery attempted' if sent else 'email delivery not configured or failed',datetime.utcnow().isoformat()))
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
            user=c.execute("SELECT password_hash FROM users WHERE id=?",(row['user_id'],)).fetchone()
            if user and check_password_hash(user['password_hash'],password):c.close();flash(text('same'));return render_template('reset_password.html')
            now=datetime.utcnow().isoformat();c.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(password),row['user_id']));c.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",(now,row['user_id']));c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(row['user_id'],'password_reset','password reset completed',now));c.commit();c.close()
            lang=session.get('lang','ar');csrf=session.get('_csrf_token');session.clear();session['lang']=lang
            if csrf:session['_csrf_token']=csrf
            flash(text('done'));return redirect(url_for('login'))
        c.close();return render_template('reset_password.html')
