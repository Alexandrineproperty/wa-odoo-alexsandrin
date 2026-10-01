import os
import xmlrpc.client
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Konfigurasi Gemini API
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Tentukan model utama resmi yang direkomendasikan Google
model = genai.GenerativeModel("gemini-3.8-flash")

# Konfigurasi Odoo
ODOO_URL = os.environ.get("ODOO_URL", "https://billbry.odoo.com")
ODOO_DB = os.environ.get("ODOO_DB", "billbry")
ODOO_USER = os.environ.get("ODOO_USER", "cvbillbrymustikakarya@gmail.com")
ODOO_PASS = os.environ.get("ODOO_PASS")

# Konfigurasi WhatsApp Cloud API
WA_TOKEN = os.environ.get("WA_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "alexsandrin123")

def simpan_crm_odoo(nama, no_hp, teks_pesan, respon_ai):
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
        if not uid:
            return None
        models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
        lead_id = models.execute_kw(
            ODOO_DB, uid, ODOO_PASS,
            'crm.lead', 'create', [{
                'name': f"WA Properti: {no_hp}",
                'contact_name': nama or no_hp,
                'mobile': no_hp,
                'description': f"Pesan Masuk: {teks_pesan}\n\nBalasan AI: {respon_ai}",
            }]
        )
        return lead_id
   def simpan_crm_odoo(nama, no_hp, teks_pesan, respon_ai):
    try:
        raw_url = os.environ.get("ODOO_URL", "https://billbry.odoo.com").strip().rstrip("/")
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            url_odoo = f"https://{raw_url}"
        else:
            url_odoo = raw_url

        common = xmlrpc.client.ServerProxy(f"{url_odoo}/xmlrpc/2/common")
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
        if not uid:
            print("Gagal otentikasi Odoo")
            return None

        models = xmlrpc.client.ServerProxy(f"{url_odoo}/xmlrpc/2/object")
        lead_id = models.execute_kw(
            ODOO_DB, uid, ODOO_PASS,
            'crm.lead', 'create', [{
                'name': f"WA Properti: {no_hp}",
                'contact_name': nama or no_hp,
                'mobile': no_hp,
                'type': 'opportunity',
                'description': f"Pesan Masuk: {teks_pesan}\n\nBalasan AI: {respon_ai}",
            }]
        )
        print(f"Berhasil simpan ke Odoo dengan Lead ID: {lead_id}")
        return lead_id
    except Exception as e:
        print(f"Gagal simpan ke Odoo: {e}")
        return None

@app.route("/webhook", methods=["GET"])
def verifikasi():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            msg_obj = entry["messages"][0]
            pengirim = msg_obj["from"]
            teks = msg_obj.get("text", {}).get("body", "")
            nama_profil = entry.get("contacts", [{}])[0].get("profile", {}).get("name", pengirim)

            # Buat balasan dengan Gemini
            prompt = (
                f"Anda adalah asisten virtual resmi Alexandrine Properti. "
                f"Balas dengan sopan, ramah, dan profesional pertanyaan calon pembeli berikut: '{teks}'"
            )
            ai_reply = model.generate_content(prompt).text

            # Kirim balasan ke WhatsApp calon pembeli
            kirim_balasan_wa(pengirim, ai_reply)

            # Rekam prospek ke CRM Odoo
            simpan_crm_odoo(nama_profil, pengirim, teks, ai_reply)
    except Exception as e:
        print(f"Error proses webhook: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
