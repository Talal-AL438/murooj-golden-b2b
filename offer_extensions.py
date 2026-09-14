from datetime import datetime, timedelta
from flask import request, redirect, url_for, render_template, flash, session, g
from werkzeug.security import generate_password_hash


def register_offer_extensions(app, db, current_user):
    app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=True)

    def ensure_schema():
        c=db()
        tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'users' in tables:
            user_cols=[r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()]
            if 'department' not in user_cols:c.execute("ALTER TABLE users ADD COLUMN department TEXT DEFAULT ''")
            c.execute("CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,ip TEXT,success INTEGER DEFAULT 0,created_at TEXT NOT NULL)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup ON login_attempts(email,ip,created_at)")
        if 'offers' in tables:
            cols=[r['name'] for r in c.execute('PRAGMA table_info(offers)').fetchall()]
            if 'image_url' not in cols:c.execute("ALTER TABLE offers ADD COLUMN image_url TEXT DEFAULT ''")
            c.execute("CREATE TABLE IF NOT EXISTS offer_targets (offer_id INTEGER NOT NULL,agency_id INTEGER NOT NULL,PRIMARY KEY(offer_id,agency_id),FOREIGN KEY(offer_id) REFERENCES offers(id),FOREIGN KEY(agency_id) REFERENCES agencies(id))")
        c.commit();c.close()

    @app.before_request
    def ensure_offer_schema():
        ensure_schema()
        if request.path=='/setup-admin' and request.method=='POST' and len(request.form.get('password',''))<8:
            flash('يجب أن تكون كلمة مرور المدير 8 أحرف على الأقل.');return redirect(url_for('setup_admin'))
        if request.path=='/login' and request.method=='POST':
            email=request.form.get('email','').strip().lower();ip=(request.headers.get('X-Forwarded-For','').split(',')[0].strip() or request.remote_addr or '')[:64];cutoff=(datetime.utcnow()-timedelta(minutes=15)).isoformat();c=db();failed=c.execute("SELECT COUNT(*) c FROM login_attempts WHERE email=? AND ip=? AND success=0 AND created_at>=?",(email,ip,cutoff)).fetchone()['c'];c.close()
            if failed>=5:g.login_rate_blocked=True;flash('تم تجاوز عدد محاولات تسجيل الدخول. حاول مرة أخرى بعد 15 دقيقة.');return redirect(url_for('login'))
        if request.path=='/register' and request.method=='POST':
            lang=request.form.get('language','ar')
            if lang not in ('ar','en','id','ms'):lang='ar'
            messages={
                'ar':{'bad':'يرجى إدخال بيانات الوكالة بشكل صحيح.','password':'يجب أن تكون كلمة المرور 8 أحرف على الأقل.','consent':'يجب الموافقة على الشروط واستقبال تحديثات WhatsApp.'},
                'en':{'bad':'Please enter valid agency details.','password':'Password must be at least 8 characters.','consent':'You must accept the terms and WhatsApp updates.'},
                'id':{'bad':'Masukkan data agen yang valid.','password':'Kata sandi minimal 8 karakter.','consent':'Anda harus menyetujui syarat dan pembaruan WhatsApp.'},
                'ms':{'bad':'Sila masukkan maklumat agensi yang sah.','password':'Kata laluan mestilah sekurang-kurangnya 8 aksara.','consent':'Anda mesti bersetuju dengan terma dan kemas kini WhatsApp.'}}
            m=messages[lang];agency=request.form.get('agency_name','').strip();country=request.form.get('country','').strip();contact=request.form.get('contact_name','').strip();wa=request.form.get('whatsapp','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','');digits=''.join(ch for ch in wa if ch.isdigit())
            if len(password)<8:flash(m['password']);return redirect(url_for('register'))
            if not request.form.get('privacy') or not request.form.get('marketing'):flash(m['consent']);return redirect(url_for('register'))
            if len(agency)<2 or len(agency)>150 or len(country)<2 or len(country)>100 or len(contact)<2 or len(contact)>120 or len(digits)<8 or len(digits)>15 or len(email)>254 or '@' not in email or '.' not in email.rsplit('@',1)[-1]:flash(m['bad']);return redirect(url_for('register'))

    @app.after_request
    def record_login_attempt(response):
        if request.path=='/login' and request.method=='POST' and not getattr(g,'login_rate_blocked',False):
            email=request.form.get('email','').strip().lower();ip=(request.headers.get('X-Forwarded-For','').split(',')[0].strip() or request.remote_addr or '')[:64];success=1 if session.get('user_id') else 0;c=db()
            if success:c.execute("DELETE FROM login_attempts WHERE email=? AND ip=?",(email,ip))
            else:c.execute("INSERT INTO login_attempts(email,ip,success,created_at) VALUES(?,?,0,?)",(email,ip,datetime.utcnow().isoformat()))
            cutoff=(datetime.utcnow()-timedelta(days=2)).isoformat();c.execute("DELETE FROM login_attempts WHERE created_at<?",(cutoff,));c.commit();c.close()
        return response

    def audit(action,details=''):
        u=current_user();c=db();c.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",(u['id'] if u else None,action,details,datetime.utcnow().isoformat()));c.commit();c.close()

    def employee_error(key):
        u=current_user();lang=(u['language'] if u else 'ar') or 'ar'
        messages={
            'ar':{'bad':'تحقق من اسم الموظف والقسم والمسمى الوظيفي والجوال والبريد الإلكتروني.','password':'كلمة المرور المؤقتة يجب أن تكون 8 أحرف على الأقل.','email':'البريد الإلكتروني مستخدم بالفعل.','saved':'تم تحديث بيانات الموظف بنجاح.','added':'تمت إضافة الموظف بنجاح.'},
            'en':{'bad':'Check the employee name, department, job title, mobile, and email.','password':'Temporary password must be at least 8 characters.','email':'This email is already in use.','saved':'Employee details updated successfully.','added':'Employee added successfully.'},
            'id':{'bad':'Periksa nama, departemen, jabatan, ponsel, dan email pegawai.','password':'Kata sandi sementara minimal 8 karakter.','email':'Email ini sudah digunakan.','saved':'Data pegawai berhasil diperbarui.','added':'Pegawai berhasil ditambahkan.'},
            'ms':{'bad':'Semak nama, jabatan, bahagian, telefon dan e-mel pekerja.','password':'Kata laluan sementara mestilah sekurang-kurangnya 8 aksara.','email':'E-mel ini telah digunakan.','saved':'Maklumat pekerja berjaya dikemas kini.','added':'Pekerja berjaya ditambah.'}}
        return messages.get(lang,messages['en'])[key]

    def valid_employee_fields(name,department,job_title,mobile,email):
        digits=''.join(ch for ch in mobile if ch.isdigit())
        return 2<=len(name)<=120 and 2<=len(department)<=100 and 2<=len(job_title)<=120 and 8<=len(digits)<=15 and len(email)<=254 and '@' in email and '.' in email.rsplit('@',1)[-1]

    def admin_employees_extended():
        ensure_schema();u=current_user()
        if not u or u['role']!='super_admin':return redirect(url_for('admin'))
        c=db()
        if request.method=='POST':
            name=request.form.get('name','').strip();department=request.form.get('department','').strip();job_title=request.form.get('job_title','').strip();mobile=request.form.get('mobile','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','')
            if not valid_employee_fields(name,department,job_title,mobile,email):c.close();flash(employee_error('bad'));return redirect(url_for('admin_employees'))
            if len(password)<8:c.close();flash(employee_error('password'));return redirect(url_for('admin_employees'))
            if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():c.close();flash(employee_error('email'));return redirect(url_for('admin_employees'))
            c.execute("INSERT INTO users(email,password_hash,role,name,job_title,mobile,department,language,active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(email,generate_password_hash(password),'staff',name,job_title,mobile,department,'ar',1,datetime.utcnow().isoformat()));c.commit();c.close();audit('employee_add',email);flash(employee_error('added'));return redirect(url_for('admin_employees'))
        employees=c.execute("SELECT * FROM users WHERE role IN ('staff','super_admin') ORDER BY CASE WHEN role='super_admin' THEN 0 ELSE 1 END,id").fetchall();c.close();return render_template('admin_employees.html',user=u,employees=employees)

    @app.route('/admin/employee/<int:uid>/edit',methods=['POST'])
    def edit_employee_extended(uid):
        ensure_schema();u=current_user()
        if not u or u['role']!='super_admin':return redirect(url_for('admin'))
        c=db();employee=c.execute("SELECT * FROM users WHERE id=? AND role='staff'",(uid,)).fetchone()
        if not employee:c.close();return 'staff not found',404
        name=request.form.get('name','').strip();department=request.form.get('department','').strip();job_title=request.form.get('job_title','').strip();mobile=request.form.get('mobile','').strip();email=request.form.get('email','').strip().lower();new_password=request.form.get('new_password','')
        if not valid_employee_fields(name,department,job_title,mobile,email):c.close();flash(employee_error('bad'));return redirect(url_for('admin_employees'))
        duplicate=c.execute('SELECT 1 FROM users WHERE email=? AND id<>?',(email,uid)).fetchone()
        if duplicate:c.close();flash(employee_error('email'));return redirect(url_for('admin_employees'))
        if new_password and len(new_password)<8:c.close();flash(employee_error('password'));return redirect(url_for('admin_employees'))
        c.execute('UPDATE users SET name=?,department=?,job_title=?,mobile=?,email=? WHERE id=?',(name,department,job_title,mobile,email,uid))
        if new_password:c.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(new_password),uid))
        c.commit();c.close();audit('employee_edit',f'employee={uid}');flash(employee_error('saved'));return redirect(url_for('admin_employees'))

    def offer_error(u,key):
        lang=(u['language'] if u else 'ar') or 'ar'
        messages={
            'ar':{'bad':'تعذر حفظ العرض. تحقق من البيانات المطلوبة.','dates':'تاريخ نهاية العرض يجب ألا يسبق تاريخ البداية.','hotel':'الفندق المحدد غير موجود أو غير نشط.','selected':'اختر وكالة واحدة على الأقل للعرض المخصص.','image':'رابط صورة العرض غير صالح.'},
            'en':{'bad':'The offer could not be saved. Check the required fields.','dates':'Offer end date cannot be before the start date.','hotel':'The selected hotel does not exist or is inactive.','selected':'Select at least one agency for a targeted offer.','image':'The offer image URL is invalid.'},
            'id':{'bad':'Penawaran tidak dapat disimpan. Periksa data wajib.','dates':'Tanggal akhir penawaran tidak boleh sebelum tanggal mulai.','hotel':'Hotel yang dipilih tidak ditemukan atau tidak aktif.','selected':'Pilih minimal satu agen untuk penawaran khusus.','image':'URL gambar penawaran tidak valid.'},
            'ms':{'bad':'Tawaran tidak dapat disimpan. Semak maklumat wajib.','dates':'Tarikh tamat tawaran tidak boleh sebelum tarikh mula.','hotel':'Hotel yang dipilih tidak wujud atau tidak aktif.','selected':'Pilih sekurang-kurangnya satu agensi untuk tawaran khusus.','image':'URL imej tawaran tidak sah.'}}
        return messages.get(lang,messages['en'])[key]

    def validate_offer(c,u):
        title=request.form.get('title','').strip();hotel_raw=request.form.get('hotel_id','').strip();start=request.form.get('start_date','').strip();end=request.form.get('end_date','').strip();meal=request.form.get('meal','').strip();note=request.form.get('note','').strip();image_url=request.form.get('image_url','').strip();audience=request.form.get('audience','all');language_mode=request.form.get('language_mode','auto');manual_language=request.form.get('manual_language','ar')
        if not title or len(title)>200 or len(note)>2000 or meal not in ('','RO','F.B Indo','F.B Malaysian'):return None,offer_error(u,'bad')
        hotel_id=None
        if hotel_raw:
            try:hotel_id=int(hotel_raw)
            except ValueError:return None,offer_error(u,'hotel')
            hotel=c.execute('SELECT id FROM hotels WHERE id=? AND active=1',(hotel_id,)).fetchone()
            if not hotel:return None,offer_error(u,'hotel')
        parsed_start=parsed_end=None
        try:
            if start:parsed_start=datetime.strptime(start,'%Y-%m-%d').date()
            if end:parsed_end=datetime.strptime(end,'%Y-%m-%d').date()
        except ValueError:return None,offer_error(u,'dates')
        if parsed_start and parsed_end and parsed_end<parsed_start:return None,offer_error(u,'dates')
        if image_url and not (image_url.startswith('/static/') or image_url.startswith('https://') or image_url.startswith('http://')):return None,offer_error(u,'image')
        if audience not in ('all','indonesia','malaysia','selected'):audience='all'
        if language_mode not in ('auto','manual'):language_mode='auto'
        if manual_language not in ('ar','en','id','ms'):manual_language='ar'
        selected=[]
        for value in request.form.getlist('selected_agencies'):
            try:selected.append(int(value))
            except ValueError:pass
        selected=list(dict.fromkeys(selected))
        if selected:
            placeholders=','.join('?' for _ in selected)
            valid_ids={r['id'] for r in c.execute(f"SELECT a.id FROM agencies a JOIN users u ON u.id=a.user_id WHERE a.id IN ({placeholders}) AND u.active=1",selected).fetchall()}
            selected=[sid for sid in selected if sid in valid_ids]
        if audience=='selected' and not selected:return None,offer_error(u,'selected')
        try:sort_order=int(request.form.get('sort_order',0))
        except ValueError:sort_order=0
        return {'title':title,'hotel_id':hotel_id,'start':start,'end':end,'meal':meal,'note':note,'image_url':image_url,'audience':audience,'language_mode':language_mode,'manual_language':manual_language,'pinned':1 if request.form.get('pinned') else 0,'sort_order':sort_order,'selected':selected},None

    def send_offer_notifications(c,oid,title,audience,selected,language_mode,manual_language):
        rows=c.execute("SELECT a.id agency_id,u.id user_id,u.language,a.country FROM agencies a JOIN users u ON u.id=a.user_id WHERE u.active=1").fetchall()
        selected=set(selected)
        labels={'ar':('عرض جديد','تمت إضافة عرض جديد: '),'en':('New offer','A new offer is available: '),'id':('Penawaran baru','Penawaran baru tersedia: '),'ms':('Tawaran baharu','Tawaran baharu tersedia: ')}
        for row in rows:
            country=(row['country'] or '').lower();allowed=audience=='all' or (audience=='indonesia' and 'indonesia' in country) or (audience=='malaysia' and 'malaysia' in country) or (audience=='selected' and row['agency_id'] in selected)
            if not allowed:continue
            lang=manual_language if language_mode=='manual' else (row['language'] or 'en');head,prefix=labels.get(lang,labels['en'])
            c.execute("INSERT INTO notifications(user_id,type,ref_id,title,body,link,created_at) VALUES(?,?,?,?,?,?,?)",(row['user_id'],'offer',oid,head,prefix+title,f'/offer/{oid}',datetime.utcnow().isoformat()))

    def home_extended():
        ensure_schema();c=db();u=current_user();today=datetime.utcnow().date().isoformat()
        hotels=c.execute("SELECT h.*,(SELECT image_url FROM hotel_images i WHERE i.hotel_id=h.id ORDER BY i.sort_order,i.id LIMIT 1) cover_image FROM hotels h WHERE h.active=1 ORDER BY h.sort_order,h.id").fetchall()
        base="""SELECT o.*,h.name_ar,h.name_en FROM offers o LEFT JOIN hotels h ON h.id=o.hotel_id WHERE o.active=1 AND (o.end_date='' OR o.end_date IS NULL OR o.end_date>=?)"""
        params=[today]
        if u and u['role']=='agency':
            agency=c.execute("SELECT id,country FROM agencies WHERE user_id=?",(u['id'],)).fetchone()
            if agency:
                country=(agency['country'] or '').lower();allowed=['all']
                if 'indonesia' in country:allowed.append('indonesia')
                if 'malaysia' in country:allowed.append('malaysia')
                placeholders=','.join('?' for _ in allowed)
                base+=f" AND (o.audience IN ({placeholders}) OR (o.audience='selected' AND EXISTS (SELECT 1 FROM offer_targets ot WHERE ot.offer_id=o.id AND ot.agency_id=?)))"
                params.extend(allowed);params.append(agency['id'])
            else:base+=" AND o.audience='all'"
        else:base+=" AND o.audience='all'"
        offers=c.execute(base+" ORDER BY o.pinned DESC,o.sort_order,o.id DESC LIMIT 6",params).fetchall();settings={r['key']:r['value'] for r in c.execute("SELECT * FROM settings").fetchall()};c.close();return render_template('home.html',hotels=hotels,offers=offers,settings=settings,user=u)

    def admin_offers_extended():
        ensure_schema();u=current_user()
        if not u or u['role'] not in ('super_admin','staff'):return redirect(url_for('login'))
        c=db()
        if request.method=='POST':
            action=request.form.get('action','add')
            if action=='toggle':
                try:oid=int(request.form.get('oid',''))
                except ValueError:c.close();flash(offer_error(u,'bad'));return redirect(url_for('admin_offers'))
                row=c.execute('SELECT active FROM offers WHERE id=?',(oid,)).fetchone()
                if not row:c.close();return 'offer not found',404
                c.execute('UPDATE offers SET active=? WHERE id=?',(0 if row['active'] else 1,oid));c.commit();c.close();audit('offer_toggle',f'offer={oid}');return redirect(url_for('admin_offers'))
            data,error=validate_offer(c,u)
            if error:c.close();flash(error);return redirect(url_for('admin_offers'))
            if action=='edit':
                try:oid=int(request.form.get('oid',''))
                except ValueError:c.close();flash(offer_error(u,'bad'));return redirect(url_for('admin_offers'))
                if not c.execute('SELECT id FROM offers WHERE id=?',(oid,)).fetchone():c.close();return 'offer not found',404
                c.execute("UPDATE offers SET title=?,hotel_id=?,start_date=?,end_date=?,meal=?,note=?,image_url=?,audience=?,language_mode=?,manual_language=?,pinned=?,sort_order=? WHERE id=?",(data['title'],data['hotel_id'],data['start'],data['end'],data['meal'],data['note'],data['image_url'],data['audience'],data['language_mode'],data['manual_language'],data['pinned'],data['sort_order'],oid));c.execute('DELETE FROM offer_targets WHERE offer_id=?',(oid,))
                if data['audience']=='selected':c.executemany('INSERT OR IGNORE INTO offer_targets(offer_id,agency_id) VALUES(?,?)',[(oid,a) for a in data['selected']])
                c.commit();c.close();audit('offer_edit',f'offer={oid}');return redirect(url_for('admin_offers'))
            cur=c.execute("INSERT INTO offers(title,hotel_id,start_date,end_date,meal,note,audience,language_mode,manual_language,active,pinned,sort_order,created_at,image_url) VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?)",(data['title'],data['hotel_id'],data['start'],data['end'],data['meal'],data['note'],data['audience'],data['language_mode'],data['manual_language'],data['pinned'],data['sort_order'],datetime.utcnow().isoformat(),data['image_url']));oid=cur.lastrowid
            if data['audience']=='selected':c.executemany('INSERT OR IGNORE INTO offer_targets(offer_id,agency_id) VALUES(?,?)',[(oid,a) for a in data['selected']])
            send_offer_notifications(c,oid,data['title'],data['audience'],data['selected'],data['language_mode'],data['manual_language']);c.commit();c.close();audit('offer_add',data['title']);return redirect(url_for('admin_offers'))
        offers=c.execute("SELECT o.*,h.name_en FROM offers o LEFT JOIN hotels h ON h.id=o.hotel_id ORDER BY o.pinned DESC,o.sort_order,o.id DESC").fetchall();hotels=c.execute('SELECT * FROM hotels WHERE active=1 ORDER BY sort_order,id').fetchall();agencies=c.execute("SELECT a.id,a.agency_name,a.country,u.email FROM agencies a JOIN users u ON u.id=a.user_id WHERE u.active=1 ORDER BY a.agency_name").fetchall();targets={}
        for r in c.execute('SELECT offer_id,agency_id FROM offer_targets').fetchall():targets.setdefault(r['offer_id'],set()).add(r['agency_id'])
        c.close();return render_template('admin_offers.html',user=u,offers=offers,hotels=hotels,agencies=agencies,offer_targets=targets)

    def offer_detail_extended(oid):
        ensure_schema();c=db();today=datetime.utcnow().date().isoformat();offer=c.execute("""SELECT o.*,h.name_ar,h.name_en,h.city,(SELECT image_url FROM hotel_images i WHERE i.hotel_id=o.hotel_id ORDER BY i.sort_order,i.id LIMIT 1) cover_image FROM offers o LEFT JOIN hotels h ON h.id=o.hotel_id WHERE o.id=? AND o.active=1 AND (o.end_date='' OR o.end_date IS NULL OR o.end_date>=?)""",(oid,today)).fetchone();c.close()
        if not offer:return 'offer not found',404
        return render_template('offer.html',offer=offer,user=current_user())

    app.view_functions['home']=home_extended
    app.view_functions['admin_offers']=admin_offers_extended
    app.view_functions['admin_employees']=admin_employees_extended
    app.view_functions['offer_detail']=offer_detail_extended
