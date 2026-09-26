import os, json, urllib.request, urllib.error
from datetime import datetime
from flask import request, redirect, url_for, render_template, flash

def register_marketing_extensions(app, db, current_user):
    def ensure_schema():
        c=db()
        cols={r['name'] for r in c.execute("PRAGMA table_info(agencies)").fetchall()}
        for name,ddl in [
            ('marketing_email',"INTEGER DEFAULT 1"),('marketing_whatsapp',"INTEGER DEFAULT 1"),
            ('new_hotel_email',"INTEGER DEFAULT 1"),('new_hotel_whatsapp',"INTEGER DEFAULT 1")]:
            if name not in cols:c.execute(f"ALTER TABLE agencies ADD COLUMN {name} {ddl}")
        c.execute("""CREATE TABLE IF NOT EXISTS offices (
          id INTEGER PRIMARY KEY AUTOINCREMENT,name_ar TEXT NOT NULL,name_en TEXT,city TEXT,address TEXT,
          phone TEXT,email TEXT,website_url TEXT,map_url TEXT,hours TEXT,active INTEGER DEFAULT 1,
          sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS marketing_campaigns (
          id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL DEFAULT 'offer',title TEXT NOT NULL,
          body TEXT,link TEXT,audience TEXT DEFAULT 'all',country TEXT,send_portal INTEGER DEFAULT 1,
          send_email INTEGER DEFAULT 0,send_whatsapp INTEGER DEFAULT 0,status TEXT DEFAULT 'draft',
          created_by INTEGER,created_at TEXT NOT NULL,sent_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS campaign_deliveries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER NOT NULL,agency_id INTEGER NOT NULL,
          channel TEXT NOT NULL,status TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL,
          UNIQUE(campaign_id,agency_id,channel))""")
        c.commit();c.close()

    @app.before_request
    def ensure_marketing_schema():ensure_schema()

    def setting(c,key,default=''):
        r=c.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return r['value'] if r else default

    def email_send(to_email,subject,body,link=''):
        api=os.environ.get('RESEND_API_KEY','').strip()
        sender=os.environ.get('MAIL_FROM','').strip()
        if not api or not sender:return False,'Email provider not configured'
        html='<div style="font-family:Arial,sans-serif"><h2>'+subject+'</h2><p>'+body+'</p>'
        if link:html+='<p><a href="'+link+'">MUROOJ GOLDEN B2B</a></p>'
        html+='</div>'
        payload=json.dumps({'from':sender,'to':[to_email],'subject':subject,'html':html}).encode()
        req=urllib.request.Request('https://api.resend.com/emails',data=payload,headers={'Authorization':'Bearer '+api,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=12) as resp:return 200<=resp.status<300,'sent'
        except Exception as e:return False,str(e)[:240]

    def whatsapp_send(number,template_name,language='ar'):
        token=os.environ.get('WHATSAPP_ACCESS_TOKEN','').strip();phone_id=os.environ.get('WHATSAPP_PHONE_NUMBER_ID','').strip()
        if not token or not phone_id or not template_name:return False,'WhatsApp Business not configured'
        digits=''.join(ch for ch in (number or '') if ch.isdigit())
        payload=json.dumps({'messaging_product':'whatsapp','to':digits,'type':'template','template':{'name':template_name,'language':{'code':language if language in ('ar','en','id','ms') else 'en'}}}).encode()
        req=urllib.request.Request('https://graph.facebook.com/v22.0/'+phone_id+'/messages',data=payload,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=12) as resp:return 200<=resp.status<300,'sent'
        except Exception as e:return False,str(e)[:240]

    def recipients(c,audience,country=''):
        sql="""SELECT a.*,u.email,u.language,u.active FROM agencies a JOIN users u ON u.id=a.user_id WHERE u.active=1"""
        params=[]
        if audience=='country' and country:sql+=" AND lower(a.country)=lower(?)";params.append(country)
        elif audience=='vip':sql+=" AND a.category='VIP'"
        return c.execute(sql,params).fetchall()

    def deliver_campaign(cid):
        c=db();camp=c.execute("SELECT * FROM marketing_campaigns WHERE id=?",(cid,)).fetchone()
        if not camp:c.close();return
        base=setting(c,'portal_public_url','https://murooj-golden-b2b.onrender.com').rstrip('/')
        link=camp['link'] or '';full_link=(base+link) if link.startswith('/') else link
        for a in recipients(c,camp['audience'],camp['country'] or ''):
            now=datetime.utcnow().isoformat()
            if camp['send_portal']:
                c.execute("INSERT INTO notifications(user_id,type,ref_id,title,body,link,created_at) VALUES(?,?,?,?,?,?,?)",(a['user_id'],'marketing',cid,camp['title'],camp['body'] or '',link or '/',now))
                c.execute("INSERT OR IGNORE INTO campaign_deliveries(campaign_id,agency_id,channel,status,detail,created_at) VALUES(?,?,?,?,?,?)",(cid,a['id'],'portal','sent','',now))
            if camp['send_email']:
                allowed=a['marketing_email'] if camp['kind']!='hotel' else a['new_hotel_email']
                if allowed:
                    ok,detail=email_send(a['email'],camp['title'],camp['body'] or '',full_link)
                    c.execute("INSERT OR REPLACE INTO campaign_deliveries(campaign_id,agency_id,channel,status,detail,created_at) VALUES(?,?,?,?,?,?)",(cid,a['id'],'email','sent' if ok else 'pending',detail,now))
            if camp['send_whatsapp']:
                allowed=a['marketing_whatsapp'] if camp['kind']!='hotel' else a['new_hotel_whatsapp']
                if allowed:
                    template=os.environ.get('WHATSAPP_NEW_HOTEL_TEMPLATE' if camp['kind']=='hotel' else 'WHATSAPP_OFFER_TEMPLATE','').strip()
                    ok,detail=whatsapp_send(a['whatsapp'],template,a['language'] or 'ar')
                    c.execute("INSERT OR REPLACE INTO campaign_deliveries(campaign_id,agency_id,channel,status,detail,created_at) VALUES(?,?,?,?,?,?)",(cid,a['id'],'whatsapp','sent' if ok else 'pending',detail,now))
        c.execute("UPDATE marketing_campaigns SET status='sent',sent_at=? WHERE id=?",(datetime.utcnow().isoformat(),cid));c.commit();c.close()

    @app.route('/offices')
    def offices():
        ensure_schema();c=db();rows=c.execute("SELECT * FROM offices WHERE active=1 ORDER BY sort_order,id").fetchall();c.close()
        return render_template('offices.html',offices=rows,user=current_user())

    @app.route('/admin/offices',methods=['GET','POST'])
    def admin_offices():
        u=current_user()
        if not u or u['role']!='super_admin':return redirect(url_for('admin'))
        ensure_schema();c=db()
        if request.method=='POST':
            action=request.form.get('action','add')
            if action=='toggle':
                oid=int(request.form['oid']);r=c.execute("SELECT active FROM offices WHERE id=?",(oid,)).fetchone()
                if r:c.execute("UPDATE offices SET active=? WHERE id=?",(0 if r['active'] else 1,oid))
            else:
                data=(request.form.get('name_ar','').strip(),request.form.get('name_en','').strip(),request.form.get('city','').strip(),request.form.get('address','').strip(),request.form.get('phone','').strip(),request.form.get('email','').strip(),request.form.get('website_url','').strip(),request.form.get('map_url','').strip(),request.form.get('hours','').strip(),int(request.form.get('sort_order',0)))
                if action=='edit':c.execute("UPDATE offices SET name_ar=?,name_en=?,city=?,address=?,phone=?,email=?,website_url=?,map_url=?,hours=?,sort_order=? WHERE id=?",data+(int(request.form['oid']),))
                else:c.execute("INSERT INTO offices(name_ar,name_en,city,address,phone,email,website_url,map_url,hours,sort_order,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",data+(datetime.utcnow().isoformat(),))
            c.commit();c.close();return redirect(url_for('admin_offices'))
        rows=c.execute("SELECT * FROM offices ORDER BY sort_order,id").fetchall();c.close();return render_template('admin_offices.html',offices=rows,user=u)

    @app.route('/admin/campaigns',methods=['GET','POST'])
    def admin_campaigns():
        u=current_user()
        if not u or u['role']!='super_admin':return redirect(url_for('admin'))
        ensure_schema();c=db()
        if request.method=='POST':
            action=request.form.get('action','create')
            if action=='send':
                cid=int(request.form['cid']);c.close();deliver_campaign(cid);flash('تم تنفيذ الحملة. القنوات غير المربوطة تبقى Pending حتى تفعيل مزود الخدمة.');return redirect(url_for('admin_campaigns'))
            cur=c.execute("""INSERT INTO marketing_campaigns(kind,title,body,link,audience,country,send_portal,send_email,send_whatsapp,status,created_by,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,'draft',?,?)""",(request.form.get('kind','offer'),request.form.get('title','').strip(),request.form.get('body','').strip(),request.form.get('link','').strip(),request.form.get('audience','all'),request.form.get('country','').strip(),1 if request.form.get('send_portal') else 0,1 if request.form.get('send_email') else 0,1 if request.form.get('send_whatsapp') else 0,u['id'],datetime.utcnow().isoformat()))
            c.commit();c.close();flash('تم حفظ الحملة التسويقية.');return redirect(url_for('admin_campaigns'))
        rows=c.execute("""SELECT m.*,
          (SELECT COUNT(*) FROM campaign_deliveries d WHERE d.campaign_id=m.id AND d.status='sent') sent_count,
          (SELECT COUNT(*) FROM campaign_deliveries d WHERE d.campaign_id=m.id AND d.status='pending') pending_count
          FROM marketing_campaigns m ORDER BY m.id DESC LIMIT 100""").fetchall();c.close();return render_template('admin_campaigns.html',campaigns=rows,user=u)

    @app.route('/admin/agency/<int:aid>/marketing',methods=['POST'])
    def agency_marketing(aid):
        u=current_user()
        if not u or u['role']!='super_admin':return redirect(url_for('admin'))
        ensure_schema();c=db();c.execute("""UPDATE agencies SET marketing_email=?,marketing_whatsapp=?,new_hotel_email=?,new_hotel_whatsapp=? WHERE id=?""",
          (1 if request.form.get('marketing_email') else 0,1 if request.form.get('marketing_whatsapp') else 0,1 if request.form.get('new_hotel_email') else 0,1 if request.form.get('new_hotel_whatsapp') else 0,aid));c.commit();c.close();return redirect(url_for('admin_agencies'))

    @app.route('/admin/hotel/<int:hid>/announce',methods=['POST'])
    def announce_hotel(hid):
        u=current_user()
        if not u or u['role']!='super_admin':return redirect(url_for('admin'))
        ensure_schema();c=db();h=c.execute("SELECT * FROM hotels WHERE id=?",(hid,)).fetchone()
        if not h:c.close();return 'hotel not found',404
        title=('فندق جديد: '+h['name_ar']);body='تمت إضافة '+h['name_ar']+' إلى بوابة مروج الذهبية B2B.'
        cur=c.execute("""INSERT INTO marketing_campaigns(kind,title,body,link,audience,country,send_portal,send_email,send_whatsapp,status,created_by,created_at)
          VALUES('hotel',?,?,?,?,?,1,?,?, 'draft',?,?)""",(title,body,'/hotel/'+str(hid),'all','',1 if request.form.get('send_email') else 0,1 if request.form.get('send_whatsapp') else 0,u['id'],datetime.utcnow().isoformat()))
        cid=cur.lastrowid;c.commit();c.close();deliver_campaign(cid);flash('تم إنشاء وإرسال إشعار الفندق الجديد حسب القنوات المحددة.');return redirect(url_for('admin_hotels'))
