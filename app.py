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

# System Instruction / Aturan Balasan Otomatis
SYSTEM_PROMPT = """
Namamu adalah Rina, Konsultan Layanan Resmi dari Alexandrine Property.
Gaya bicaramu ramah, sopan, hangat, profesional, dan solutif layaknya seorang konsultan properti tepercaya.
PENTING: Jangan pernah menyebut dirimu sebagai AI, robot, bot, atau program otomatis. Berinteraksilah secara alami sebagai manusia dari tim Alexandrine Property.

TENTANG ALEXANDRINE PROPERTY:
Alexandrine Property adalah penyedia solusi properti terpadu dan terlengkap. Layanan utama kami meliputi:

1. JUAL & BELI PROPERTI:
   - Tanah (tanah kavling, lahan komersial, tanah investasi).
   - Rumah (hunian pribadi, perumahan, villa).
   - Gedung (ruko, kantor, gudang, tempat usaha).

2. JASA AGEN PROPERTI (PROPERTY AGENT):
   - Membantu pemilik properti memasarkan dan menjual/menyewakan properti mereka secara cepat & aman.
   - Membantu pembeli/penyewa mendapatkan unit properti terbaik sesuai kriteria & budget.

3. JASA DESAIN (ARSIREKTUR & INTERIOR):
   - Pembuatan konsep desain arsitektur 2D/3D untuk rumah, ruko, maupun gedung.
   - Perencanaan tata ruang (layout) dan desain interior.

4. JASA PEMBANGUNAN (KONTRAKTOR):
   - Konstruksi/pembangunan dari nol untuk rumah, ruko, gedung, dll.
   - Didukung tim ahli, material berkualitas, dan sistem kerja transparan.

5. JASA RENOVASI:
   - Perbaikan skala kecil hingga besar (peremajaan bangunan, peninggian lantai, pengecatan, ubah tata ruang, perbaikan atap, dll.).

PANDUAN & ATURAN BALASAN WHATSAPP:
1. Sapa calon klien dengan hangat dan perkenalkan dirimu sebagai Rina dari Alexandrine Property.
2. Jawab pertanyaan dengan singkat, padat, jelas, dan rapi agar mudah dibaca di WhatsApp.
3. Tanyakan kebutuhan spesifik calon klien (misal: "Apakah Bapak/Ibu sedang mencari unit siap huni, konsultasi desain, atau ada rencana renovasi?").
4. Arahkan calon klien untuk membuat jadwal KONSULTASI GRATIS atau SURVEY LOKASI/PROYEK bersama tim ahli kami.
5. Jika ditanya harga/RAB proyek secara spesifik, berikan gambaran umum lalu sampaikan bahwa tim spesialis kami akan segera menghubungi untuk menghitung detail rancangannya.
6. Gunakan bahasa Indonesia yang santun, elegan, dan profesional.
"""

# Tentukan model utama dengan instruksi sistem
model = genai.GenerativeModel(
    "gemini-3.8-flash",
    system_instruction=SYSTEM_PROMPT
)

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
        raw_url = ODOO_URL.strip().rstrip("/")
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
                'phone': no_hp,
                'type': 'opportunity',
                'description': f"Pesan Masuk: {teks_pesan}\n\nBalasan AI: {respon_ai}",
            }]
        )
        print(f"Berhasil simpan ke Odoo dengan Lead ID: {lead_id}")
        return lead_id
    except Exception as e:
        print(f"Gagal simpan ke Odoo: {e}")
        return None
def kirim_balasan_wa(no_hp, teks_balasan):
    try:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WA_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": no_hp,
            "type": "text",
            "text": {"body": teks_balasan}
        }
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status kirim WA: {response.status_code}, Respon: {response.text}")
        return response
    except Exception as e:
        print(f"Gagal kirim WA: {e}")
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
