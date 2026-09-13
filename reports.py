from io import BytesIO
from datetime import datetime
from flask import request, render_template, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def register_reports(app, admin_required, db, current_user):
    @app.before_request
    def save_extended_announcement_settings():
        if request.path != '/admin/settings' or request.method != 'POST':
            return None
        u=current_user()
        if not u or u['role']!='super_admin':
            return None
        c=db()
        values={
            'announcement_active':'1' if request.form.get('announcement_active') else '0',
            'announcement_target':request.form.get('announcement_target','all') if request.form.get('announcement_target','all') in ('all','indonesia','malaysia') else 'all',
            'announcement_start':request.form.get('announcement_start','').strip(),
            'announcement_end':request.form.get('announcement_end','').strip(),
            'announcement_whatsapp':'1' if request.form.get('announcement_whatsapp') else '0',
        }
        for key,value in values.items():
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value))
        c.commit();c.close()
        return None

    @app.context_processor
    def extended_portal_context():
        u=current_user(); country=''
        if u and u['role']=='agency':
            c=db(); row=c.execute("SELECT country FROM agencies WHERE user_id=?",(u['id'],)).fetchone(); c.close()
            if row: country=row['country'] or ''
        return {'agency_country':country,'current_date':datetime.utcnow().date().isoformat()}

    def filters():
        return {
            'country': request.args.get('country','').strip(),
            'hotel': request.args.get('hotel','').strip(),
            'status': request.args.get('status','').strip(),
            'from': request.args.get('from','').strip(),
            'to': request.args.get('to','').strip(),
        }

    def query_rows(c, f):
        sql="""SELECT r.*,a.agency_name,a.country,a.contact_name,a.whatsapp,u.email,
                 h.name_ar,h.name_en
                 FROM requests r
                 JOIN agencies a ON a.id=r.agency_id
                 JOIN users u ON u.id=a.user_id
                 LEFT JOIN hotels h ON h.id=r.hotel_id WHERE 1=1"""
        params=[]
        if f['country']:
            sql+=' AND a.country LIKE ?'; params.append('%'+f['country']+'%')
        if f['hotel']:
            sql+=" AND (h.name_ar LIKE ? OR h.name_en LIKE ? OR (r.any_hotel=1 AND ? LIKE '%any%'))"
            params += ['%'+f['hotel']+'%','%'+f['hotel']+'%',f['hotel'].lower()]
        if f['status'] in ('sent','contacted','closed'):
            sql+=' AND r.status=?'; params.append(f['status'])
        if f['from']:
            sql+=' AND substr(r.created_at,1,10)>=?'; params.append(f['from'])
        if f['to']:
            sql+=' AND substr(r.created_at,1,10)<=?'; params.append(f['to'])
        sql+=' ORDER BY r.id DESC'
        return c.execute(sql,params).fetchall()

    @app.route('/admin/reports')
    @admin_required
    def admin_reports():
        f=filters(); c=db(); rows=query_rows(c,f)
        summary={
            'requests':len(rows),
            'rooms':sum((r['rooms'] or 0) for r in rows),
            'persons':sum((r['persons'] or 0) for r in rows),
            'agencies':len(set(r['agency_id'] for r in rows)),
        }
        countries=c.execute("SELECT country,COUNT(*) total FROM agencies GROUP BY country ORDER BY total DESC,country").fetchall()
        hotels=c.execute("""SELECT COALESCE(h.name_en,'Any Available Hotel') hotel,COUNT(*) total
                            FROM requests r LEFT JOIN hotels h ON h.id=r.hotel_id
                            GROUP BY COALESCE(h.name_en,'Any Available Hotel') ORDER BY total DESC""").fetchall()
        c.close()
        return render_template('admin_reports.html',user=current_user(),rows=rows,summary=summary,filters=f,countries=countries,hotels=hotels)

    @app.route('/admin/reports.xlsx')
    @admin_required
    def admin_reports_excel():
        f=filters(); c=db(); rows=query_rows(c,f); c.close()
        wb=Workbook(); ws=wb.active; ws.title='Requests'
        headers=['Request ID','Agency','Country','Contact','WhatsApp','Email','Hotel','City','Check-in','Check-out','Rooms','Persons','Nationality','Meal','Status','Created At']
        ws.append(headers)
        for cell in ws[1]:
            cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='111111'); cell.alignment=Alignment(horizontal='center')
        for r in rows:
            hotel='Any Available Hotel' if r['any_hotel'] else (r['name_en'] or r['name_ar'] or '')
            ws.append([r['id'],r['agency_name'],r['country'],r['contact_name'],r['whatsapp'],r['email'],hotel,r['city'],r['checkin'],r['checkout'],r['rooms'],r['persons'],r['nationality'],r['meal'],r['status'],r['created_at']])
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for i in range(1,len(headers)+1):
            max_len=max(len(str(ws.cell(row=j,column=i).value or '')) for j in range(1,min(ws.max_row,500)+1))
            ws.column_dimensions[get_column_letter(i)].width=min(max(max_len+2,12),32)
        summary=wb.create_sheet('Summary')
        summary.append(['MUROOJ GOLDEN B2B','Report Summary']); summary.append(['Requests',len(rows)]); summary.append(['Rooms',sum((r['rooms'] or 0) for r in rows)]); summary.append(['Persons',sum((r['persons'] or 0) for r in rows)]); summary.append(['Agencies',len(set(r['agency_id'] for r in rows))])
        summary['A1'].font=Font(bold=True); summary['B1'].font=Font(bold=True)
        out=BytesIO(); wb.save(out); out.seek(0)
        return send_file(out,as_attachment=True,download_name='murooj-golden-full-report.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
