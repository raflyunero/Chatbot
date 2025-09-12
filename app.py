from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template, flash
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import os
from datetime import datetime
import sqlite3
import requests   # tambahkan untuk tes koneksi API

# Import Zhipu AI
from zai import ZhipuAiClient

# Setup Flask app
app = Flask(__name__, static_folder="static", static_url_path='')
CORS(app)

# Load environment variables
load_dotenv()

# Admin credentials (from .env file)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# API Key Zhipu AI
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
client = ZhipuAiClient(api_key=ZHIPU_API_KEY)

# Hashing password default untuk admin
hashed_password = bcrypt.hashpw("BORIGANTENG".encode('utf-8'), bcrypt.gensalt())

# ---------------- Database Setup ---------------- #
def get_db():
    conn = sqlite3.connect('questions.db')
    return conn

def create_table_if_not_exists():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_count (
            date TEXT PRIMARY KEY,
            count INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_question():
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.today().strftime('%Y-%m-%d')
    cursor.execute("SELECT count FROM question_count WHERE date = ?", (today,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE question_count SET count = count + 1 WHERE date = ?", (today,))
    else:
        cursor.execute("INSERT INTO question_count (date, count) VALUES (?, ?)", (today, 1))
    conn.commit()
    conn.close()

def get_today_question_count():
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.today().strftime('%Y-%m-%d')
    cursor.execute("SELECT count FROM question_count WHERE date = ?", (today,))
    row = cursor.fetchone()
    count = row[0] if row else 0
    conn.close()
    return count

# ---------------- Helper ---------------- #
def verify_password(input_password, stored_hash):
    return bcrypt.checkpw(input_password.encode('utf-8'), stored_hash)

# Fungsi untuk jawab pertanyaan pakai Zhipu AI
def get_undip_response(user_message):
    try:
        response = client.chat.completions.create(
            model="glm-4.5",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Lo sekarang jadi chatbot akademik Universitas Diponegoro (UNDIP). "
                        "Jawaban lo wajib pake bahasa santai, gaul, ala anak muda jaman sekarang 🤙, "
                        "tapi tetep sopan, singkat, jelas, dan gak keluar konteks akademik. "
                        "Lo cuma boleh jawab pertanyaan yang nyangkut sama UNDIP doang, "
                        "kayak fakultas, prodi, jadwal kuliah, dosen, layanan akademik, pendaftaran, "
                        "beasiswa, penelitian, dan semua layanan resmi yang ada di kampus. "
                        "Kalo ada yang nanya di luar topik UNDIP, tolak dengan halus tapi tetep chill."
                    ),
                },
                {"role": "user", "content": user_message}
            ],
            thinking={"type": "enabled"},
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error:", e)
        return "Maaf, terjadi kesalahan saat menghubungi server Zhipu AI."

# ---------------- Routes ---------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == ADMIN_USERNAME and verify_password(password, hashed_password):
            session["logged_in"] = True
            return redirect(url_for("admin"))
        else:
            flash("Login gagal! Username atau password salah.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# Route chatbot API
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message", "")
    save_question()
    reply = get_undip_response(user_message)
    return jsonify({"reply": reply})

# 🔹 Tambahkan fungsi cek koneksi API
def check_zhipu_connection():
    try:
        headers = {"Authorization": f"Bearer {ZHIPU_API_KEY}"}
        resp = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json={
                "model": "glm-4",
                "messages": [{"role": "user", "content": "ping"}]
            },
            timeout=5
        )
        return resp.status_code == 200
    except Exception as e:
        print("Gagal koneksi ke Zhipu:", e)
        return False

@app.route('/admin/dashboard')
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    create_table_if_not_exists()
    today_question_count = get_today_question_count()
    zhipu_connected = check_zhipu_connection()
    return render_template("admin_panel.html", question_count=today_question_count, zhipu_connected=zhipu_connected)

@app.route("/get_questions_today", methods=["GET"])
def get_questions_today():
    today_question_count = get_today_question_count()
    return jsonify({"today_question_count": today_question_count})

@app.route('/admin/monitoring')
def monitoring_faq():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template('monitoring_faq.html')

@app.route('/admin/change-password', methods=['GET', 'POST'])
def change_password():
    global hashed_password

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if verify_password(old_password, hashed_password) and new_password == confirm_password:
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            flash("Password berhasil diubah!", "success")
            return redirect(url_for('admin'))
        else:
            flash("Password tidak sesuai atau tidak cocok!", "error")

    return render_template('change_password.html')

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    create_table_if_not_exists()
    today_question_count = get_today_question_count()
    zhipu_connected = check_zhipu_connection()
    return render_template("admin_panel.html", question_count=today_question_count, zhipu_connected=zhipu_connected)

# ---------------- Main ---------------- #
if __name__ == "__main__":
    app.secret_key = os.getenv("SECRET_KEY", "default_secret")
    app.run(debug=True)
