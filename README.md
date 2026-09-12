# MUROOJ GOLDEN B2B — V2 Operational Local Build

This version adds a real local backend using Flask + SQLite.

## Included
- Persistent SQLite database.
- Agency registration and login.
- Mandatory privacy + WhatsApp marketing consent.
- Four-language selector: Arabic, English, Bahasa Indonesia, Bahasa Melayu.
- Agency request history.
- Request statuses limited to: Sent → Contacted via WhatsApp → Closed.
- Makkah hotel data for Nada Ajyad and Sawaeed Al Khair.
- Admin dashboard, agencies, hotels, offers, employees, settings.
- Offer language mode: automatic per agency or manual language.
- Super Admin-only audit log and employee/settings controls.
- Temporary admin email: talal_alaqely@icloud.com.
- WhatsApp direct links.
- No prices, official booking numbers, vouchers, invoices, or payment confirmation.

## First run
1. Install Python 3.11+.
2. Open a terminal in this folder.
3. Run:
   pip install -r requirements.txt
   python app.py
4. Open:
   http://127.0.0.1:5000/setup-admin
5. Create the Super Admin password yourself.
6. Then use:
   http://127.0.0.1:5000

## Important before public deployment
This local V2 is operational for testing, but public deployment still needs:
- a strong SECRET_KEY environment variable,
- HTTPS hosting,
- production WSGI server,
- automated database backups,
- real password-reset email delivery,
- WhatsApp Business/API for automatic outbound WhatsApp campaigns,
- tighter staff permission granularity,
- image upload storage and hotel gallery management,
- privacy/legal review appropriate to the markets in which you operate.

No paid service is required to run this version locally.
