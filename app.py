
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3, os, secrets
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "murooj.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-public-deployment")

LANGS = {
    "ar": {
        "portal":"بوابة مروج الذهبية B2B","home":"الرئيسية","hotels":"الفنادق","offers":"العروض","quick_request":"طلب سريع",
        "login":"تسجيل الدخول","register":"تسجيل وكالة","logout":"تسجيل الخروج","account":"حسابي","admin":"لوحة الإدارة",
        "hero":"شريكك الموثوق لحجوزات الفنادق","sub":"مكة المكرمة والمدينة المنورة — بوابة مخصصة لوكالات السفر والحج والعمرة.",
        "makkah":"مكة المكرمة","madinah":"المدينة المنورة","view":"عرض الفندق","location":"الموقع","send_request":"إرسال طلب",
        "agency_name":"اسم الوكالة","country":"الدولة","contact_name":"اسم المسؤول","whatsapp":"رقم WhatsApp","email":"البريد الإلكتروني",
        "password":"كلمة المرور","privacy":"أوافق على الشروط وسياسة الخصوصية","marketing":"أوافق على استقبال العروض والتحديثات التسويقية عبر WhatsApp",
        "create_account":"إنشاء الحساب","checkin":"تاريخ الدخول","checkout":"تاريخ الخروج","rooms":"عدد الغرف","persons":"عدد الأشخاص",
        "nationality":"جنسية المجموعة","meal":"الوجبات","notes":"ملاحظات","status":"الحالة","repeat":"تكرار الطلب",
        "sent":"تم الإرسال","contacted":"تم التواصل عبر WhatsApp","closed":"مغلق","submit":"إرسال","search":"بحث",
        "new_requests":"طلبات جديدة","agencies":"الوكالات","reports":"التقارير","employees":"الموظفون والصلاحيات","settings":"الإعدادات",
        "audit":"سجل العمليات","save":"حفظ","add":"إضافة","edit":"تعديل","hide":"إخفاء","show":"إظهار","language":"اللغة",
        "any_hotel":"أي فندق متاح","room_only":"بدون وجبات","indo_fb":"وجبات إندونيسية كاملة","malay_fb":"وجبات ماليزية كاملة",
        "success_request":"تم إرسال طلبك إلى مروج الذهبية بنجاح. سيتواصل معك فريق الحجوزات عبر WhatsApp لتأكيد التوفر والسعر.",
        "welcome":"مرحبًا","special_offers":"العروض الخاصة","city":"المدينة","hotel":"الفندق","actions":"الإجراءات","date":"التاريخ",
        "job_title":"المسمى الوظيفي","mobile":"رقم الجوال","role":"الدور","active":"نشط","suspended":"موقوف","verified":"موثقة",
        "category":"التصنيف","last_request":"آخر طلب","request_count":"عدد الطلبات","registration_date":"تاريخ التسجيل","no_active_offers":"لا توجد عروض نشطة حالياً"
    },
    "en": {
        "portal":"Murooj Golden B2B Portal","home":"Home","hotels":"Hotels","offers":"Offers","quick_request":"Quick Request",
        "login":"Login","register":"Register Agency","logout":"Logout","account":"My Account","admin":"Admin",
        "hero":"Your Trusted Hotel Booking Partner","sub":"Makkah & Madinah — a B2B portal for travel, Hajj and Umrah agencies.",
        "makkah":"Makkah","madinah":"Madinah","view":"View Hotel","location":"Location","send_request":"Send Request",
        "agency_name":"Agency Name","country":"Country","contact_name":"Contact Person","whatsapp":"WhatsApp Number","email":"Email",
        "password":"Password","privacy":"I agree to the Terms and Privacy Policy","marketing":"I agree to receive offers and marketing updates via WhatsApp",
        "create_account":"Create Account","checkin":"Check-in","checkout":"Check-out","rooms":"Rooms","persons":"Persons",
        "nationality":"Group Nationality","meal":"Meal Plan","notes":"Notes","status":"Status","repeat":"Repeat Request",
        "sent":"Sent","contacted":"Contacted via WhatsApp","closed":"Closed","submit":"Submit","search":"Search",
        "new_requests":"New Requests","agencies":"Agencies","reports":"Reports","employees":"Users & Permissions","settings":"Settings",
        "audit":"Audit Log","save":"Save","add":"Add","edit":"Edit","hide":"Hide","show":"Show","language":"Language",
        "any_hotel":"Any Available Hotel","room_only":"Room Only","indo_fb":"Indonesian Full Board","malay_fb":"Malaysian Full Board",
        "success_request":"Your request was sent to Murooj Golden successfully. Our reservations team will contact you on WhatsApp to confirm availability and price.",
        "welcome":"Welcome","special_offers":"Special Offers","city":"City","hotel":"Hotel","actions":"Actions","date":"Date",
        "job_title":"Job Title","mobile":"Mobile","role":"Role","active":"Active","suspended":"Suspended","verified":"Verified",
        "category":"Category","last_request":"Last Request","request_count":"Requests","registration_date":"Registered"
    },
    "id": {
        "portal":"Portal B2B Murooj Golden","home":"Beranda","hotels":"Hotel","offers":"Penawaran","quick_request":"Permintaan Cepat",
        "login":"Masuk","register":"Daftar Agen","logout":"Keluar","account":"Akun Saya","admin":"Admin",
        "hero":"Mitra Tepercaya untuk Pemesanan Hotel","sub":"Makkah & Madinah — portal B2B untuk agen perjalanan, Haji dan Umrah.",
        "makkah":"Makkah","madinah":"Madinah","view":"Lihat Hotel","location":"Lokasi","send_request":"Kirim Permintaan",
        "agency_name":"Nama Agen","country":"Negara","contact_name":"Nama Kontak","whatsapp":"Nomor WhatsApp","email":"Email",
        "password":"Kata Sandi","privacy":"Saya menyetujui Syarat dan Kebijakan Privasi","marketing":"Saya setuju menerima penawaran dan pembaruan pemasaran via WhatsApp",
        "create_account":"Buat Akun","checkin":"Check-in","checkout":"Check-out","rooms":"Jumlah Kamar","persons":"Jumlah Orang",
        "nationality":"Kewarganegaraan Grup","meal":"Paket Makan","notes":"Catatan","status":"Status","repeat":"Ulangi Permintaan",
        "sent":"Terkirim","contacted":"Dihubungi via WhatsApp","closed":"Ditutup","submit":"Kirim","search":"Cari",
        "new_requests":"Permintaan Baru","agencies":"Agen","reports":"Laporan","employees":"Pengguna & Izin","settings":"Pengaturan",
        "audit":"Log Aktivitas","save":"Simpan","add":"Tambah","edit":"Edit","hide":"Sembunyikan","show":"Tampilkan","language":"Bahasa",
        "any_hotel":"Hotel Apa Saja yang Tersedia","room_only":"Tanpa Makan","indo_fb":"Full Board Indonesia","malay_fb":"Full Board Malaysia",
        "success_request":"Permintaan Anda berhasil dikirim ke Murooj Golden. Tim reservasi akan menghubungi Anda melalui WhatsApp untuk mengonfirmasi ketersediaan dan harga.",
        "welcome":"Selamat datang","special_offers":"Penawaran Khusus","city":"Kota","hotel":"Hotel","actions":"Aksi","date":"Tanggal",
        "job_title":"Jabatan","mobile":"Ponsel","role":"Peran","active":"Aktif","suspended":"Ditangguhkan","verified":"Terverifikasi",
        "category":"Kategori","last_request":"Permintaan Terakhir","request_count":"Jumlah Permintaan","registration_date":"Tanggal Daftar"
    },
    "ms": {
        "portal":"Portal B2B Murooj Golden","home":"Utama","hotels":"Hotel","offers":"Tawaran","quick_request":"Permintaan Pantas",
        "login":"Log Masuk","register":"Daftar Agensi","logout":"Log Keluar","account":"Akaun Saya","admin":"Pentadbir",
        "hero":"Rakan Dipercayai untuk Tempahan Hotel","sub":"Makkah & Madinah — portal B2B untuk agensi pelancongan, Haji dan Umrah.",
        "makkah":"Makkah","madinah":"Madinah","view":"Lihat Hotel","location":"Lokasi","send_request":"Hantar Permintaan",
        "agency_name":"Nama Agensi","country":"Negara","contact_name":"Nama Pegawai","whatsapp":"Nombor WhatsApp","email":"E-mel",
        "password":"Kata Laluan","privacy":"Saya bersetuju dengan Terma dan Dasar Privasi","marketing":"Saya bersetuju menerima tawaran dan kemas kini pemasaran melalui WhatsApp",
        "create_account":"Cipta Akaun","checkin":"Daftar Masuk","checkout":"Daftar Keluar","rooms":"Bilangan Bilik","persons":"Bilangan Orang",
        "nationality":"Kewarganegaraan Kumpulan","meal":"Pelan Makanan","notes":"Catatan","status":"Status","repeat":"Ulang Permintaan",
        "sent":"Dihantar","contacted":"Dihubungi melalui WhatsApp","closed":"Ditutup","submit":"Hantar","search":"Cari",
        "new_requests":"Permintaan Baharu","agencies":"Agensi","reports":"Laporan","employees":"Pengguna & Kebenaran","settings":"Tetapan",
        "audit":"Log Aktiviti","save":"Simpan","add":"Tambah","edit":"Edit","hide":"Sembunyi","show":"Tunjuk","language":"Bahasa",
        "any_hotel":"Mana-mana Hotel Tersedia","room_only":"Tanpa Makanan","indo_fb":"Papan Penuh Indonesia","malay_fb":"Papan Penuh Malaysia",
        "success_request":"Permintaan anda berjaya dihantar kepada Murooj Golden. Pasukan tempahan akan menghubungi anda melalui WhatsApp untuk mengesahkan ketersediaan dan harga.",
        "welcome":"Selamat datang","special_offers":"Tawaran Istimewa","city":"Bandar","hotel":"Hotel","actions":"Tindakan","date":"Tarikh",
        "job_title":"Jawatan","mobile":"Telefon","role":"Peranan","active":"Aktif","suspended":"Digantung","verified":"Disahkan",
        "category":"Kategori","last_request":"Permintaan Terakhir","request_count":"Jumlah Permintaan","registration_date":"Tarikh Daftar"
    }
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'agency', name TEXT, job_title TEXT, mobile TEXT,
      language TEXT DEFAULT 'ar', active INTEGER DEFAULT 1, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS agencies (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL,
      agency_name TEXT NOT NULL, country TEXT NOT NULL, contact_name TEXT NOT NULL,
      whatsapp TEXT NOT NULL, category TEXT DEFAULT 'New', verified INTEGER DEFAULT 0,
      internal_notes TEXT DEFAULT '', marketing_consent INTEGER DEFAULT 1,
      created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS hotels (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT NOT NULL, name_en TEXT NOT NULL,
      city TEXT NOT NULL, map_url TEXT, services TEXT, meals TEXT, active INTEGER DEFAULT 1,
      sort_order INTEGER DEFAULT 0, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT, agency_id INTEGER NOT NULL, hotel_id INTEGER,
      any_hotel INTEGER DEFAULT 0, city TEXT NOT NULL, checkin TEXT, checkout TEXT,
      rooms INTEGER, persons INTEGER, nationality TEXT, meal TEXT, notes TEXT,
      status TEXT DEFAULT 'sent', created_at TEXT NOT NULL,
      FOREIGN KEY(agency_id) REFERENCES agencies(id), FOREIGN KEY(hotel_id) REFERENCES hotels(id)
    );
    CREATE TABLE IF NOT EXISTS offers (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, hotel_id INTEGER,
      start_date TEXT, end_date TEXT, meal TEXT, note TEXT, audience TEXT DEFAULT 'all',
      language_mode TEXT DEFAULT 'auto', manual_language TEXT DEFAULT 'ar',
      active INTEGER DEFAULT 1, pinned INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL,
      details TEXT, created_at TEXT NOT NULL
    );
    """)
    defaults = {
      "company_name":"مروج الذهبية للاستثمار",
      "brand":"MUROOJ GOLDEN",
      "whatsapp":"966550558014",
      "email":"talal_alaqely@icloud.com",
      "announcement":"",
      "announcement_active":"0"
    }
    for k,v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",(k,v))
    count = conn.execute("SELECT COUNT(*) c FROM hotels").fetchone()["c"]
    if count == 0:
        now = datetime.utcnow().isoformat()
        conn.execute("""INSERT INTO hotels(name_ar,name_en,city,map_url,services,meals,active,sort_order,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                     ("فندق ندى أجياد","NADA AJYAD HOTEL","Makkah",
                      "https://maps.app.goo.gl/PzgRgz23LRDex1Wq7?g_st=iw",
                      "Wi‑Fi|استقبال 24 ساعة|مصاعد|تكييف|مطعم|تنظيف الغرف|ثلاجة|تلفزيون",
                      "RO|F.B Indo|F.B Malaysian",1,1,now))
        conn.execute("""INSERT INTO hotels(name_ar,name_en,city,map_url,services,meals,active,sort_order,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                     ("فندق سواعد الخير","SAWAEED AL KHAIR HOTEL","Makkah",
                      "https://maps.app.goo.gl/GcA7zZYftYcuYx9N6?g_st=iw",
                      "Wi‑Fi|استقبال 24 ساعة|مصاعد|تكييف|مطعم|تنظيف الغرف|ثلاجة|تلفزيون",
                      "RO|F.B Indo|F.B Malaysian",1,2,now))
    conn.commit(); conn.close()

@app.before_request
def ensure():
    init_db()

def t():
    lang = session.get("lang","ar")
    return LANGS.get(lang, LANGS["ar"])

@app.context_processor
def inject():
    return {"T": t(), "lang": session.get("lang","ar")}

def current_user():
    uid = session.get("user_id")
    if not uid: return None
    conn=db(); u=conn.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); conn.close()
    return u

def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not current_user(): return redirect(url_for("login"))
        return f(*a, **kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        u=current_user()
        if not u or u["role"] not in ("super_admin","staff"): return redirect(url_for("login"))
        return f(*a, **kw)
    return w

def super_required(f):
    @wraps(f)
    def w(*a, **kw):
        u=current_user()
        if not u or u["role"]!="super_admin": return redirect(url_for("admin"))
        return f(*a, **kw)
    return w

def log(action, details=""):
    u=current_user()
    conn=db()
    conn.execute("INSERT INTO audit(user_id,action,details,created_at) VALUES(?,?,?,?)",
                 (u["id"] if u else None, action, details, datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

@app.route("/lang/<code>")
def set_lang(code):
    if code in LANGS: session["lang"]=code
    return redirect(request.referrer or url_for("home"))

@app.route("/")
def home():
    conn=db()
    hotels=conn.execute("SELECT * FROM hotels WHERE active=1 ORDER BY sort_order,id").fetchall()
    offers=conn.execute("""SELECT o.*,h.name_ar,h.name_en FROM offers o
                          LEFT JOIN hotels h ON h.id=o.hotel_id WHERE o.active=1
                          ORDER BY o.pinned DESC,o.sort_order,o.id DESC LIMIT 6""").fetchall()
    settings={r["key"]:r["value"] for r in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close()
    return render_template("home.html", hotels=hotels, offers=offers, settings=settings, user=current_user())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        if not request.form.get("privacy") or not request.form.get("marketing"):
            flash("Both privacy and WhatsApp marketing consent are required.")
            return redirect(url_for("register"))
        email=request.form["email"].strip().lower()
        conn=db()
        if conn.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone():
            conn.close(); flash("Email already registered."); return redirect(url_for("register"))
        now=datetime.utcnow().isoformat()
        cur=conn.execute("""INSERT INTO users(email,password_hash,role,name,mobile,language,created_at)
                            VALUES(?,?,?,?,?,?,?)""",
                         (email,generate_password_hash(request.form["password"]),"agency",
                          request.form["contact_name"],request.form["whatsapp"],
                          request.form.get("language","ar"),now))
        uid=cur.lastrowid
        conn.execute("""INSERT INTO agencies(user_id,agency_name,country,contact_name,whatsapp,marketing_consent,created_at)
                        VALUES(?,?,?,?,?,?,?)""",
                     (uid,request.form["agency_name"],request.form["country"],request.form["contact_name"],
                      request.form["whatsapp"],1,now))
        conn.commit(); conn.close()
        session["user_id"]=uid; session["lang"]=request.form.get("language","ar")
        return redirect(url_for("account"))
    return render_template("register.html", user=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        conn=db(); u=conn.execute("SELECT * FROM users WHERE email=?",(request.form["email"].strip().lower(),)).fetchone(); conn.close()
        if u and u["active"] and check_password_hash(u["password_hash"],request.form["password"]):
            session["user_id"]=u["id"]; session["lang"]=u["language"] or "ar"
            return redirect(url_for("admin" if u["role"] in ("super_admin","staff") else "account"))
        flash("Invalid login or suspended account.")
    return render_template("login.html", user=current_user())

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/setup-admin", methods=["GET","POST"])
def setup_admin():
    conn=db()
    exists=conn.execute("SELECT 1 FROM users WHERE role='super_admin'").fetchone()
    if exists:
        conn.close(); return redirect(url_for("login"))
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        if email!="talal_alaqely@icloud.com":
            conn.close(); flash("Use the approved temporary admin email."); return redirect(url_for("setup_admin"))
        conn.execute("""INSERT INTO users(email,password_hash,role,name,language,created_at)
                      VALUES(?,?,?,?,?,?)""",
                     (email,generate_password_hash(request.form["password"]),"super_admin",
                      request.form.get("name","Super Admin"),"ar",datetime.utcnow().isoformat()))
        conn.commit(); conn.close()
        flash("Super Admin account created. You can now log in.")
        return redirect(url_for("login"))
    conn.close(); return render_template("setup_admin.html", user=None)

@app.route("/request", methods=["GET","POST"])
@login_required
def new_request():
    u=current_user()
    if u["role"]!="agency": return redirect(url_for("admin"))
    conn=db()
    agency=conn.execute("SELECT * FROM agencies WHERE user_id=?",(u["id"],)).fetchone()
    hotels=conn.execute("SELECT * FROM hotels WHERE active=1 ORDER BY sort_order,id").fetchall()
    if request.method=="POST":
        hotel_val=request.form.get("hotel_id","")
        any_hotel = 1 if hotel_val=="any" else 0
        hotel_id = None if any_hotel else int(hotel_val)
        conn.execute("""INSERT INTO requests(agency_id,hotel_id,any_hotel,city,checkin,checkout,rooms,persons,nationality,meal,notes,status,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (agency["id"],hotel_id,any_hotel,request.form["city"],request.form["checkin"],request.form["checkout"],
                      int(request.form["rooms"]),int(request.form["persons"]),request.form["nationality"],
                      request.form["meal"],request.form.get("notes",""),"sent",datetime.utcnow().isoformat()))
        conn.commit()
        flash(t()["success_request"])
        conn.close()
        return redirect(url_for("account"))
    conn.close()
    return render_template("request.html", hotels=hotels, user=u)

@app.route("/account", methods=["GET","POST"])
@login_required
def account():
    u=current_user()
    if u["role"]!="agency": return redirect(url_for("admin"))
    conn=db()
    agency=conn.execute("SELECT * FROM agencies WHERE user_id=?",(u["id"],)).fetchone()
    if request.method=="POST":
        action=request.form.get("action","")
        messages={
          "ar":{"profile":"تم تحديث بيانات الحساب بنجاح.","password":"تم تغيير كلمة المرور بنجاح.","bad_password":"كلمة المرور الحالية غير صحيحة.","short":"يجب أن تكون كلمة المرور الجديدة 8 أحرف على الأقل."},
          "en":{"profile":"Account details updated successfully.","password":"Password changed successfully.","bad_password":"Current password is incorrect.","short":"New password must be at least 8 characters."},
          "id":{"profile":"Data akun berhasil diperbarui.","password":"Kata sandi berhasil diubah.","bad_password":"Kata sandi saat ini salah.","short":"Kata sandi baru minimal 8 karakter."},
          "ms":{"profile":"Maklumat akaun berjaya dikemas kini.","password":"Kata laluan berjaya ditukar.","bad_password":"Kata laluan semasa tidak betul.","short":"Kata laluan baharu mestilah sekurang-kurangnya 8 aksara."}
        }
        msg=messages.get(session.get("lang","ar"),messages["ar"])
        if action=="profile":
            contact_name=request.form.get("contact_name","").strip()
            country=request.form.get("country","").strip()
            whatsapp=request.form.get("whatsapp","").strip()
            if contact_name and country and whatsapp:
                conn.execute("UPDATE agencies SET contact_name=?,country=?,whatsapp=? WHERE id=?",(contact_name,country,whatsapp,agency["id"]))
                conn.execute("UPDATE users SET name=?,mobile=? WHERE id=?",(contact_name,whatsapp,u["id"]))
                conn.commit(); flash(msg["profile"])
        elif action=="password":
            current_password=request.form.get("current_password","")
            new_password=request.form.get("new_password","")
            if not check_password_hash(u["password_hash"],current_password):
                flash(msg["bad_password"])
            elif len(new_password)<8:
                flash(msg["short"])
            else:
                conn.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(new_password),u["id"]))
                conn.commit(); flash(msg["password"])
        conn.close()
        return redirect(url_for("account"))
    reqs=conn.execute("""SELECT r.*,h.name_ar,h.name_en FROM requests r
                        LEFT JOIN hotels h ON h.id=r.hotel_id WHERE r.agency_id=? ORDER BY r.id DESC""",(agency["id"],)).fetchall()
    conn.close()
    return render_template("account.html", user=u, agency=agency, reqs=reqs)

@app.route("/admin")
@admin_required
def admin():
    conn=db()
    stats={
      "agencies":conn.execute("SELECT COUNT(*) c FROM agencies").fetchone()["c"],
      "new":conn.execute("SELECT COUNT(*) c FROM requests WHERE status='sent'").fetchone()["c"],
      "requests":conn.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"],
      "hotels":conn.execute("SELECT COUNT(*) c FROM hotels WHERE active=1").fetchone()["c"]
    }
    reqs=conn.execute("""SELECT r.*,a.agency_name,a.country,a.whatsapp,h.name_ar,h.name_en
                        FROM requests r JOIN agencies a ON a.id=r.agency_id
                        LEFT JOIN hotels h ON h.id=r.hotel_id ORDER BY r.id DESC LIMIT 50""").fetchall()
    conn.close()
    return render_template("admin.html", user=current_user(), stats=stats, reqs=reqs)

@app.route("/admin/request/<int:rid>/status", methods=["POST"])
@admin_required
def update_request_status(rid):
    status=request.form["status"]
    if status not in ("sent","contacted","closed"): return "bad status",400
    conn=db(); conn.execute("UPDATE requests SET status=? WHERE id=?",(status,rid)); conn.commit(); conn.close()
    log("request_status", f"request={rid}, status={status}")
    return redirect(url_for("admin"))

@app.route("/admin/hotels", methods=["GET","POST"])
@admin_required
def admin_hotels():
    conn=db()
    if request.method=="POST":
        conn.execute("""INSERT INTO hotels(name_ar,name_en,city,map_url,services,meals,active,sort_order,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                     (request.form["name_ar"],request.form["name_en"],request.form["city"],request.form.get("map_url",""),
                      request.form.get("services",""),request.form.get("meals",""),1,int(request.form.get("sort_order",0)),datetime.utcnow().isoformat()))
        conn.commit(); log("hotel_add", request.form["name_en"])
    hotels=conn.execute("SELECT * FROM hotels ORDER BY sort_order,id").fetchall(); conn.close()
    return render_template("admin_hotels.html", user=current_user(), hotels=hotels)

@app.route("/admin/hotel/<int:hid>/toggle", methods=["POST"])
@admin_required
def hotel_toggle(hid):
    conn=db(); row=conn.execute("SELECT active FROM hotels WHERE id=?",(hid,)).fetchone()
    conn.execute("UPDATE hotels SET active=? WHERE id=?",(0 if row["active"] else 1,hid)); conn.commit(); conn.close()
    log("hotel_toggle", f"hotel={hid}")
    return redirect(url_for("admin_hotels"))

@app.route("/admin/offers", methods=["GET","POST"])
@admin_required
def admin_offers():
    conn=db()
    if request.method=="POST":
        conn.execute("""INSERT INTO offers(title,hotel_id,start_date,end_date,meal,note,audience,language_mode,manual_language,active,pinned,sort_order,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (request.form["title"], request.form.get("hotel_id") or None, request.form.get("start_date",""),request.form.get("end_date",""),
                      request.form.get("meal",""),request.form.get("note",""),request.form.get("audience","all"),
                      request.form.get("language_mode","auto"),request.form.get("manual_language","ar"),1,
                      1 if request.form.get("pinned") else 0,int(request.form.get("sort_order",0)),datetime.utcnow().isoformat()))
        conn.commit(); log("offer_add", request.form["title"])
    offers=conn.execute("""SELECT o.*,h.name_en FROM offers o LEFT JOIN hotels h ON h.id=o.hotel_id ORDER BY o.pinned DESC,o.sort_order,o.id DESC""").fetchall()
    hotels=conn.execute("SELECT * FROM hotels WHERE active=1 ORDER BY sort_order,id").fetchall()
    conn.close()
    return render_template("admin_offers.html", user=current_user(), offers=offers, hotels=hotels)

@app.route("/admin/agencies", methods=["GET","POST"])
@admin_required
def admin_agencies():
    conn=db()
    if request.method=="POST":
        try:
            aid=int(request.form.get("aid","0"))
        except ValueError:
            conn.close(); return "bad agency",400
        agency=conn.execute("SELECT * FROM agencies WHERE id=?",(aid,)).fetchone()
        if not agency:
            conn.close(); return "agency not found",404
        action=request.form.get("action","save")
        if action=="save":
            category=request.form.get("category","New")
            if category not in ("New","Active","VIP","Suspended"):
                conn.close(); return "bad category",400
            verified=1 if request.form.get("verified") else 0
            notes=request.form.get("internal_notes","").strip()
            conn.execute("UPDATE agencies SET category=?,verified=?,internal_notes=? WHERE id=?",(category,verified,notes,aid))
            conn.execute("UPDATE users SET active=? WHERE id=?",(0 if category=="Suspended" else 1,agency["user_id"]))
        elif action=="toggle":
            user=conn.execute("SELECT active FROM users WHERE id=?",(agency["user_id"],)).fetchone()
            new_active=0 if user and user["active"] else 1
            conn.execute("UPDATE users SET active=? WHERE id=?",(new_active,agency["user_id"]))
            if not new_active:
                conn.execute("UPDATE agencies SET category='Suspended' WHERE id=?",(aid,))
            elif agency["category"]=="Suspended":
                conn.execute("UPDATE agencies SET category='Active' WHERE id=?",(aid,))
        else:
            conn.close(); return "bad action",400
        conn.commit(); conn.close()
        log("agency_update", f"agency={aid}, action={action}")
        return redirect(url_for("admin_agencies"))

    q=request.args.get("q","").strip()
    sql="""SELECT a.*,u.email,u.active,
           (SELECT COUNT(*) FROM requests r WHERE r.agency_id=a.id) request_count,
           (SELECT MAX(created_at) FROM requests r WHERE r.agency_id=a.id) last_request
           FROM agencies a JOIN users u ON u.id=a.user_id"""
    params=[]
    if q:
        sql += " WHERE a.agency_name LIKE ? OR a.country LIKE ? OR a.contact_name LIKE ? OR u.email LIKE ?"
        params=[f"%{q}%"]*4
    sql += " ORDER BY a.id DESC"
    agencies=conn.execute(sql,params).fetchall(); conn.close()
    return render_template("admin_agencies.html", user=current_user(), agencies=agencies, q=q)

@app.route("/admin/employees", methods=["GET","POST"])
@super_required
def admin_employees():
    conn=db()
    if request.method=="POST":
        email=request.form["email"].strip().lower()
        if not conn.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone():
            conn.execute("""INSERT INTO users(email,password_hash,role,name,job_title,mobile,language,active,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                         (email,generate_password_hash(request.form["password"]),"staff",request.form["name"],
                          request.form["job_title"],request.form["mobile"],"ar",1,datetime.utcnow().isoformat()))
            conn.commit(); log("employee_add", email)
    employees=conn.execute("SELECT * FROM users WHERE role IN ('staff','super_admin') ORDER BY id").fetchall(); conn.close()
    return render_template("admin_employees.html", user=current_user(), employees=employees)

@app.route("/admin/settings", methods=["GET","POST"])
@super_required
def admin_settings():
    conn=db()
    if request.method=="POST":
        for key in ("company_name","brand","whatsapp","email","announcement","announcement_active"):
            if key in request.form:
                conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                             (key,request.form[key]))
        conn.commit(); log("settings_update","general settings")
    settings={r["key"]:r["value"] for r in conn.execute("SELECT * FROM settings").fetchall()}; conn.close()
    return render_template("admin_settings.html", user=current_user(), settings=settings)

@app.route("/admin/audit")
@super_required
def admin_audit():
    conn=db()
    rows=conn.execute("""SELECT a.*,u.email,u.name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 300""").fetchall()
    conn.close()
    return render_template("admin_audit.html", user=current_user(), rows=rows)

@app.route("/health")
def health():
    return jsonify({"ok":True})

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
