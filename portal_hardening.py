from functools import wraps
from datetime import datetime
from flask import request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash


def apply_portal_hardening(app, db):
    """Validation layer for agency registration, booking, account security and hotel gallery ordering."""

    def msg(ar, en, id_text=None, ms=None):
        lang=session.get('lang','ar')
        return {'ar':ar,'en':en,'id':id_text or en,'ms':ms or en}.get(lang,ar)

    original_register=app.view_functions.get('register')
    if original_register:
        @wraps(original_register)
        def safe_register(*args, **kwargs):
            if request.method=='POST':
                password=request.form.get('password','')
                language=request.form.get('language','ar')
                required=('agency_name','country','contact_name','whatsapp','email')
                if any(not request.form.get(k,'').strip() for k in required):
                    flash(msg('يرجى إكمال جميع الحقول المطلوبة.','Please complete all required fields.','Silakan lengkapi semua kolom wajib.','Sila lengkapkan semua medan wajib.'))
                    return redirect(url_for('register'))
                if len(password)<8:
                    flash(msg('يجب أن تكون كلمة المرور 8 أحرف على الأقل.','Password must be at least 8 characters.','Kata sandi minimal 8 karakter.','Kata laluan mestilah sekurang-kurangnya 8 aksara.'))
                    return redirect(url_for('register'))
                if language not in ('ar','en','id','ms'):
                    flash(msg('اللغة المختارة غير صالحة.','Invalid language selection.'))
                    return redirect(url_for('register'))
            return original_register(*args,**kwargs)
        app.view_functions['register']=safe_register

    original_request=app.view_functions.get('new_request')
    if original_request:
        @wraps(original_request)
        def safe_request(*args, **kwargs):
            if request.method=='POST':
                try:
                    rooms=int(request.form.get('rooms','0'));persons=int(request.form.get('persons','0'))
                except (TypeError,ValueError):
                    rooms=persons=0
                checkin=request.form.get('checkin','');checkout=request.form.get('checkout','');city=request.form.get('city','')
                try:
                    d1=datetime.strptime(checkin,'%Y-%m-%d').date();d2=datetime.strptime(checkout,'%Y-%m-%d').date()
                except (TypeError,ValueError):
                    d1=d2=None
                if rooms<1 or persons<1 or not d1 or not d2 or d2<=d1:
                    flash(msg('تحقق من التواريخ وعدد الغرف والأشخاص. يجب أن يكون تاريخ الخروج بعد تاريخ الدخول.','Check the dates, rooms and persons. Check-out must be after check-in.','Periksa tanggal, kamar, dan jumlah orang. Check-out harus setelah check-in.','Semak tarikh, bilik dan bilangan orang. Daftar keluar mesti selepas daftar masuk.'))
                    return redirect(request.referrer or url_for('home',_anchor='hotels'))
                if city not in ('Makkah','Madinah'):
                    flash(msg('المدينة المختارة غير صالحة.','Invalid city selection.','Pilihan kota tidak valid.','Pilihan bandar tidak sah.'))
                    return redirect(url_for('home',_anchor='hotels'))
                hv=request.form.get('hotel_id','')
                if hv!='any':
                    try:hid=int(hv)
                    except (TypeError,ValueError):hid=0
                    c=db();hotel=c.execute('SELECT id,city FROM hotels WHERE id=? AND active=1',(hid,)).fetchone();c.close()
                    if not hotel or hotel['city']!=city:
                        flash(msg('الفندق المختار غير متاح حالياً. اختر الفندق مرة أخرى.','The selected hotel is not currently available. Please choose again.','Hotel yang dipilih saat ini tidak tersedia. Silakan pilih lagi.','Hotel yang dipilih tidak tersedia buat masa ini. Sila pilih semula.'))
                        return redirect(url_for('home',_anchor='hotels'))
            return original_request(*args,**kwargs)
        app.view_functions['new_request']=safe_request

    original_account=app.view_functions.get('account')
    if original_account:
        @wraps(original_account)
        def safe_account(*args, **kwargs):
            if request.method=='POST' and request.form.get('action')=='password':
                new=request.form.get('new_password','');confirm=request.form.get('confirm_password','')
                if len(new)<8:
                    flash(msg('يجب أن تكون كلمة المرور الجديدة 8 أحرف على الأقل.','New password must be at least 8 characters.','Kata sandi baru minimal 8 karakter.','Kata laluan baharu mestilah sekurang-kurangnya 8 aksara.'))
                    return redirect(url_for('account'))
                if new!=confirm:
                    flash(msg('كلمتا المرور الجديدتان غير متطابقتين.','New passwords do not match.','Kata sandi baru tidak cocok.','Kata laluan baharu tidak sepadan.'))
                    return redirect(url_for('account'))
                uid=session.get('user_id')
                if uid and new:
                    c=db();u=c.execute('SELECT password_hash FROM users WHERE id=?',(uid,)).fetchone();c.close()
                    if u and check_password_hash(u['password_hash'],new):
                        flash(msg('اختر كلمة مرور جديدة مختلفة عن الحالية.','Choose a new password different from the current one.','Pilih kata sandi baru yang berbeda dari kata sandi saat ini.','Pilih kata laluan baharu yang berbeza daripada kata laluan semasa.'))
                        return redirect(url_for('account'))
            return original_account(*args,**kwargs)
        app.view_functions['account']=safe_account

    original_hotels=app.view_functions.get('admin_hotels')
    if original_hotels:
        @wraps(original_hotels)
        def safe_admin_hotels(*args, **kwargs):
            if request.method=='POST' and request.form.get('action')=='image_order':
                uid=session.get('user_id');c=db();u=c.execute('SELECT role FROM users WHERE id=? AND active=1',(uid,)).fetchone() if uid else None
                if not u or u['role'] not in ('super_admin','staff'):
                    c.close();return redirect(url_for('login'))
                try:iid=int(request.form.get('image_id','0'));order=max(0,int(request.form.get('image_sort_order','0')))
                except (TypeError,ValueError):
                    c.close();return redirect(url_for('admin_hotels'))
                row=c.execute('SELECT id FROM hotel_images WHERE id=?',(iid,)).fetchone()
                if row:
                    c.execute('UPDATE hotel_images SET sort_order=? WHERE id=?',(order,iid));c.commit()
                c.close();return redirect(url_for('admin_hotels'))
            return original_hotels(*args,**kwargs)
        app.view_functions['admin_hotels']=safe_admin_hotels
