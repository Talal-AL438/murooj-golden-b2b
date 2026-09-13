from datetime import datetime
from flask import request, redirect, url_for, render_template


def register_offer_extensions(mod):
    app,db,current_user=mod.app,mod.db,mod.current_user
    c=db()
    cols=[r['name'] for r in c.execute('PRAGMA table_info(offers)').fetchall()]
    if 'image_url' not in cols:c.execute("ALTER TABLE offers ADD COLUMN image_url TEXT DEFAULT ''")
    c.execute("CREATE TABLE IF NOT EXISTS offer_targets (offer_id INTEGER NOT NULL,agency_id INTEGER NOT NULL,PRIMARY KEY(offer_id,agency_id),FOREIGN KEY(offer_id) REFERENCES offers(id),FOREIGN KEY(agency_id) REFERENCES agencies(id))")
    c.commit();c.close()

    def send_offer_notifications(c,oid,title,audience,selected,language_mode,manual_language):
        rows=c.execute("SELECT a.id agency_id,u.id user_id,u.language,a.country FROM agencies a JOIN users u ON u.id=a.user_id WHERE u.active=1").fetchall()
        selected=set(selected)
        labels={'ar':('عرض جديد','تمت إضافة عرض جديد: '),'en':('New offer','A new offer is available: '),'id':('Penawaran baru','Penawaran baru tersedia: '),'ms':('Tawaran baharu','Tawaran baharu tersedia: ')}
        for row in rows:
            country=(row['country'] or '').lower();allowed=audience=='all' or (audience=='indonesia' and 'indonesia' in country) or (audience=='malaysia' and 'malaysia' in country) or (audience=='selected' and row['agency_id'] in selected)
            if not allowed:continue
            lang=manual_language if language_mode=='manual' else (row['language'] or 'en');head,prefix=labels.get(lang,labels['en'])
            c.execute("INSERT INTO notifications(user_id,type,ref_id,title,body,link,created_at) VALUES(?,?,?,?,?,?,?)",(row['user_id'],'offer',oid,head,prefix+title,f'/offer/{oid}',datetime.utcnow().isoformat()))

    def admin_offers_extended():
        u=current_user()
        if not u or u['role'] not in ('super_admin','staff'):return redirect(url_for('login'))
        c=db()
        if request.method=='POST':
            action=request.form.get('action','add')
            if action=='toggle':
                oid=int(request.form['oid']);row=c.execute('SELECT active FROM offers WHERE id=?',(oid,)).fetchone()
                if not row:c.close();return 'offer not found',404
                c.execute('UPDATE offers SET active=? WHERE id=?',(0 if row['active'] else 1,oid));c.commit();c.close();mod.log('offer_toggle',f'offer={oid}');return redirect(url_for('admin_offers'))
            title=request.form.get('title','').strip();hotel_id=request.form.get('hotel_id') or None;start=request.form.get('start_date','');end=request.form.get('end_date','');meal=request.form.get('meal','').strip();note=request.form.get('note','').strip();image_url=request.form.get('image_url','').strip();audience=request.form.get('audience','all');language_mode=request.form.get('language_mode','auto');manual_language=request.form.get('manual_language','ar');pinned=1 if request.form.get('pinned') else 0
            try:sort_order=int(request.form.get('sort_order',0))
            except ValueError:sort_order=0
            if audience not in ('all','indonesia','malaysia','selected'):audience='all'
            if language_mode not in ('auto','manual'):language_mode='auto'
            if manual_language not in ('ar','en','id','ms'):manual_language='ar'
            selected=[]
            for value in request.form.getlist('selected_agencies'):
                try:selected.append(int(value))
                except ValueError:pass
            if action=='edit':
                oid=int(request.form['oid']);c.execute("UPDATE offers SET title=?,hotel_id=?,start_date=?,end_date=?,meal=?,note=?,image_url=?,audience=?,language_mode=?,manual_language=?,pinned=?,sort_order=? WHERE id=?",(title,hotel_id,start,end,meal,note,image_url,audience,language_mode,manual_language,pinned,sort_order,oid));c.execute('DELETE FROM offer_targets WHERE offer_id=?',(oid,))
                if audience=='selected':c.executemany('INSERT OR IGNORE INTO offer_targets(offer_id,agency_id) VALUES(?,?)',[(oid,a) for a in selected])
                c.commit();c.close();mod.log('offer_edit',f'offer={oid}');return redirect(url_for('admin_offers'))
            cur=c.execute("INSERT INTO offers(title,hotel_id,start_date,end_date,meal,note,audience,language_mode,manual_language,active,pinned,sort_order,created_at,image_url) VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?)",(title,hotel_id,start,end,meal,note,audience,language_mode,manual_language,pinned,sort_order,datetime.utcnow().isoformat(),image_url));oid=cur.lastrowid
            if audience=='selected':c.executemany('INSERT OR IGNORE INTO offer_targets(offer_id,agency_id) VALUES(?,?)',[(oid,a) for a in selected])
            send_offer_notifications(c,oid,title,audience,selected,language_mode,manual_language);c.commit();c.close();mod.log('offer_add',title);return redirect(url_for('admin_offers'))
        offers=c.execute("SELECT o.*,h.name_en FROM offers o LEFT JOIN hotels h ON h.id=o.hotel_id ORDER BY o.pinned DESC,o.sort_order,o.id DESC").fetchall();hotels=c.execute('SELECT * FROM hotels WHERE active=1 ORDER BY sort_order,id').fetchall();agencies=c.execute("SELECT a.id,a.agency_name,a.country,u.email FROM agencies a JOIN users u ON u.id=a.user_id WHERE u.active=1 ORDER BY a.agency_name").fetchall();targets={}
        for r in c.execute('SELECT offer_id,agency_id FROM offer_targets').fetchall():targets.setdefault(r['offer_id'],set()).add(r['agency_id'])
        c.close();return render_template('admin_offers.html',user=u,offers=offers,hotels=hotels,agencies=agencies,offer_targets=targets)

    def offer_detail_extended(oid):
        c=db();today=datetime.utcnow().date().isoformat();offer=c.execute("""SELECT o.*,h.name_ar,h.name_en,h.city,(SELECT image_url FROM hotel_images i WHERE i.hotel_id=o.hotel_id ORDER BY i.sort_order,i.id LIMIT 1) cover_image FROM offers o LEFT JOIN hotels h ON h.id=o.hotel_id WHERE o.id=? AND o.active=1 AND (o.end_date='' OR o.end_date IS NULL OR o.end_date>=?)""",(oid,today)).fetchone();c.close()
        if not offer:return 'offer not found',404
        return render_template('offer.html',offer=offer,user=current_user())

    app.view_functions['admin_offers']=admin_offers_extended
    app.view_functions['offer_detail']=offer_detail_extended
