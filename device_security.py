from datetime import datetime, timedelta
import hashlib
import secrets
from flask import request, redirect, url_for, render_template, flash, session, g, make_response


def register_device_security(app, db, current_user):
    COOKIE_NAME='mg_admin_device'

    def token_hash(token):
        return hashlib.sha256((token or '').encode('utf-8')).hexdigest()

    def ensure_tables():
        c=db()
        c.execute("CREATE TABLE IF NOT EXISTS trusted_admin_devices (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT NOT NULL UNIQUE,user_agent TEXT,created_at TEXT NOT NULL,last_seen_at TEXT,approved_by INTEGER,active INTEGER DEFAULT 1,FOREIGN KEY(user_id) REFERENCES users(id))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_trusted_admin_devices_user ON trusted_admin_devices(user_id,active)")
        c.execute("CREATE TABLE IF NOT EXISTS pending_admin_devices (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token_hash TEXT NOT NULL,user_agent TEXT,ip TEXT,created_at TEXT NOT NULL,approved_at TEXT,approved_by INTEGER,rejected_at TEXT,FOREIGN KEY(user_id) REFERENCES users(id))")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_admin_devices_user ON pending_admin_devices(user_id,approved_at,rejected_at)")
        c.commit();c.close()

    def client_ip():
        return (request.headers.get('X-Forwarded-For','').split(',')[0].strip() or request.remote_addr or '')[:64]

    def current_device_row(user_id):
        token=request.cookies.get(COOKIE_NAME,'')
        if not token:return None
        c=db();row=c.execute("SELECT * FROM trusted_admin_devices WHERE user_id=? AND token_hash=? AND active=1",(user_id,token_hash(token))).fetchone();c.close();return row

    def trusted_count(user_id):
        c=db();count=c.execute("SELECT COUNT(*) c FROM trusted_admin_devices WHERE user_id=? AND active=1",(user_id,)).fetchone()['c'];c.close();return count

    def trust_current_device(user_id, approved_by=None):
        raw=secrets.token_urlsafe(32);now=datetime.utcnow().isoformat();c=db();c.execute("INSERT INTO trusted_admin_devices(user_id,token_hash,user_agent,created_at,last_seen_at,approved_by,active) VALUES(?,?,?,?,?,?,1)",(user_id,token_hash(raw),(request.headers.get('User-Agent') or '')[:300],now,now,approved_by));c.commit();c.close();g.set_admin_device_cookie=raw

    @app.before_request
    def enforce_admin_device():
        ensure_tables()
        if request.path=='/login' and request.method=='POST':
            ip=client_ip();cutoff=(datetime.utcnow()-timedelta(minutes=15)).isoformat();c=db();failed_ip=c.execute("SELECT COUNT(*) c FROM login_attempts WHERE ip=? AND success=0 AND created_at>=?",(ip,cutoff)).fetchone()['c'];c.close()
            if failed_ip>=20:
                g.login_rate_blocked=True;flash('تم تجاوز عدد محاولات تسجيل الدخول من هذا الاتصال. حاول مرة أخرى بعد 15 دقيقة.');return redirect(url_for('login'))
        if request.path.startswith('/static/'):return None
        u=current_user()
        if not u or u['role'] not in ('super_admin','staff'):return None
        if session.get('_pending_admin_device_id'):
            if request.endpoint in ('admin_device_verification','logout'):return None
            return redirect(url_for('admin_device_verification'))
        row=current_device_row(u['id'])
        if row:
            c=db();c.execute("UPDATE trusted_admin_devices SET last_seen_at=? WHERE id=?",(datetime.utcnow().isoformat(),row['id']));c.commit();c.close();return None
        if trusted_count(u['id'])==0:
            trust_current_device(u['id'],u['id']);return None
        lang=u['language'] or 'ar';session.clear();session['lang']=lang;flash('هذا جهاز جديد. سجّل الدخول مرة أخرى لطلب اعتماده.' if lang=='ar' else 'This is a new device. Sign in again to request approval.');return redirect(url_for('login'))

    @app.after_request
    def admin_device_after(response):
        ensure_tables()
        if request.path=='/login' and request.method=='POST' and session.get('user_id'):
            u=current_user()
            if u and u['role'] in ('super_admin','staff') and not current_device_row(u['id']):
                if trusted_count(u['id'])==0:
                    trust_current_device(u['id'],u['id'])
                else:
                    raw=secrets.token_urlsafe(32);now=datetime.utcnow().isoformat();c=db();cur=c.execute("INSERT INTO pending_admin_devices(user_id,token_hash,user_agent,ip,created_at) VALUES(?,?,?,?,?)",(u['id'],token_hash(raw),(request.headers.get('User-Agent') or '')[:300],client_ip(),now));pid=cur.lastrowid;c.commit();c.close();session['_pending_admin_device_id']=pid;session['_pending_admin_device_token']=raw;response=make_response(redirect(url_for('admin_device_verification')))
        raw=getattr(g,'set_admin_device_cookie',None)
        if raw:
            response.set_cookie(COOKIE_NAME,raw,max_age=60*60*24*180,secure=True,httponly=True,samesite='Lax')
        return response

    @app.route('/admin/device-verification')
    def admin_device_verification():
        pid=session.get('_pending_admin_device_id');raw=session.get('_pending_admin_device_token')
        if not pid or not raw:return redirect(url_for('login'))
        c=db();row=c.execute("SELECT p.*,u.email,u.name,u.role FROM pending_admin_devices p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.token_hash=?",(pid,token_hash(raw))).fetchone()
        if not row:c.close();session.pop('_pending_admin_device_id',None);session.pop('_pending_admin_device_token',None);return redirect(url_for('login'))
        if row['rejected_at']:
            c.close();lang=session.get('lang','ar');session.clear();session['lang']=lang;flash('تم رفض اعتماد هذا الجهاز.' if lang=='ar' else 'This device approval request was rejected.');return redirect(url_for('login'))
        if row['approved_at']:
            now=datetime.utcnow().isoformat();c.execute("INSERT INTO trusted_admin_devices(user_id,token_hash,user_agent,created_at,last_seen_at,approved_by,active) VALUES(?,?,?,?,?,?,1)",(row['user_id'],row['token_hash'],row['user_agent'],now,now,row['approved_by']));c.execute("DELETE FROM pending_admin_devices WHERE id=?",(pid,));c.commit();c.close();session.pop('_pending_admin_device_id',None);session.pop('_pending_admin_device_token',None);resp=make_response(redirect(url_for('admin')));resp.set_cookie(COOKIE_NAME,raw,max_age=60*60*24*180,secure=True,httponly=True,samesite='Lax');return resp
        c.close();return render_template('admin_device_verification.html',user=current_user(),request_id=pid)

    @app.route('/admin/device-requests')
    def admin_device_requests():
        u=current_user()
        if not u or u['role']!='super_admin' or session.get('_pending_admin_device_id') or not current_device_row(u['id']):return redirect(url_for('admin'))
        c=db();rows=c.execute("SELECT p.*,u.email,u.name,u.role FROM pending_admin_devices p JOIN users u ON u.id=p.user_id WHERE p.approved_at IS NULL AND p.rejected_at IS NULL ORDER BY p.id DESC").fetchall();trusted=c.execute("SELECT d.*,u.email,u.name FROM trusted_admin_devices d JOIN users u ON u.id=d.user_id WHERE d.active=1 ORDER BY d.last_seen_at DESC").fetchall();c.close();return render_template('admin_device_requests.html',user=u,requests=rows,trusted_devices=trusted)

    @app.route('/admin/device-request/<int:pid>/approve',methods=['POST'])
    def approve_admin_device(pid):
        u=current_user()
        if not u or u['role']!='super_admin' or session.get('_pending_admin_device_id') or not current_device_row(u['id']):return redirect(url_for('admin'))
        c=db();row=c.execute("SELECT id,user_id FROM pending_admin_devices WHERE id=? AND approved_at IS NULL AND rejected_at IS NULL",(pid,)).fetchone()
        if not row:c.close();return 'device request not found',404
        c.execute("UPDATE pending_admin_devices SET approved_at=?,approved_by=? WHERE id=?",(datetime.utcnow().isoformat(),u['id'],pid));c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(u['id'],'admin_device_approve',f"request={pid}, user={row['user_id']}",datetime.utcnow().isoformat()));c.commit();c.close();flash('تم اعتماد الجهاز الجديد.');return redirect(url_for('admin_device_requests'))

    @app.route('/admin/device-request/<int:pid>/reject',methods=['POST'])
    def reject_admin_device(pid):
        u=current_user()
        if not u or u['role']!='super_admin' or session.get('_pending_admin_device_id') or not current_device_row(u['id']):return redirect(url_for('admin'))
        c=db();row=c.execute("SELECT id,user_id FROM pending_admin_devices WHERE id=? AND approved_at IS NULL AND rejected_at IS NULL",(pid,)).fetchone()
        if not row:c.close();return 'device request not found',404
        c.execute("UPDATE pending_admin_devices SET rejected_at=?,approved_by=? WHERE id=?",(datetime.utcnow().isoformat(),u['id'],pid));c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(u['id'],'admin_device_reject',f"request={pid}, user={row['user_id']}",datetime.utcnow().isoformat()));c.commit();c.close();flash('تم رفض الجهاز الجديد.');return redirect(url_for('admin_device_requests'))

    @app.route('/admin/device/<int:did>/revoke',methods=['POST'])
    def revoke_admin_device(did):
        u=current_user()
        if not u or u['role']!='super_admin' or session.get('_pending_admin_device_id') or not current_device_row(u['id']):return redirect(url_for('admin'))
        c=db();row=c.execute("SELECT id,user_id,token_hash FROM trusted_admin_devices WHERE id=? AND active=1",(did,)).fetchone()
        if not row:c.close();return 'device not found',404
        current=request.cookies.get(COOKIE_NAME,'')
        if row['user_id']==u['id'] and current and token_hash(current)==row['token_hash']:
            c.close();flash('لا يمكن إلغاء الجهاز الحالي أثناء استخدامه.');return redirect(url_for('admin_device_requests'))
        c.execute("UPDATE trusted_admin_devices SET active=0 WHERE id=?",(did,));c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(u['id'],'admin_device_revoke',f"device={did}, user={row['user_id']}",datetime.utcnow().isoformat()));c.commit();c.close();flash('تم إلغاء اعتماد الجهاز.');return redirect(url_for('admin_device_requests'))
