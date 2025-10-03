from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template, flash
from flask_cors import CORS
from dotenv import load_dotenv
from pathlib import Path
import bcrypt
import os
from datetime import datetime, timedelta
import sqlite3
import json
import random
from fuzzywuzzy import fuzz
# Import Zhipu AI
from zai import ZhipuAiClient
# ---------------- Setup Flask App ---------------- #
app = Flask(__name__, static_folder="static", static_url_path='')
CORS(app)
# Load .env
dotenv_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path)
app.secret_key = os.getenv("SECRET_KEY", "default_secret")
app.permanent_session_lifetime = timedelta(hours=2)
# ---------------- Credentials & API ---------------- #
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_HASHED_PASSWORD = os.getenv("ADMIN_HASHED_PASSWORD")
if ADMIN_HASHED_PASSWORD:
    ADMIN_HASHED_PASSWORD = ADMIN_HASHED_PASSWORD.encode("utf-8")  # convert string to bytes for bcrypt
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
client = ZhipuAiClient(api_key=ZHIPU_API_KEY)
# ---------------- Load Dataset JSON ---------------- #
dataset_dosen_data = {}
try:
    with open("dataset_dosen.json", "r", encoding="utf-8") as f:
        dataset_dosen_data = json.load(f)
except Exception as e:
    print("⚠ Gagal load dataset_dosen.json:", e)
# ---------------- Database Setup ---------------- #
def get_db():
    return sqlite3.connect("questions.db")
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
    today = datetime.today().strftime("%Y-%m-%d")
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
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT count FROM question_count WHERE date = ?", (today,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0
# ---------------- API Connection Check ---------------- #
def check_api_connection():
    if not ZHIPU_API_KEY:
        return False
    try:
        # Tes request dummy ke Zhipu
        response = client.chat.completions.create(
            model="glm-4.5",
            messages=[{"role": "user", "content": "ping"}],
        )
        if response and response.choices:
            return True
        return False
    except Exception as e:
        print("⚠ API check failed:", e)
        return False
# ---------------- RAG / Zhipu AI ---------------- #
def handle_zhipu_ai_with_rag(user_message: str):
    relevant_info = retrieve_relevant_info(user_message)
    augmented_prompt = f"""
Informasi relevan dari database UNDIP:
{relevant_info}
Pertanyaan pengguna: {user_message}
"""
    response = client.chat.completions.create(
        model="glm-4.5",
        messages=[
            {"role": "system", "content": (
                "Lo sekarang jadi chatbot akademik Universitas Diponegoro (UNDIP). "
                "Jawaban lo wajib pake bahasa santai, gaul, ala anak muda jaman sekarang 🤙, "
                "tapi tetep sopan, singkat, jelas, dan gak keluar konteks akademik."
            )},
            {"role": "user", "content": augmented_prompt}
        ],
    )
    return response.choices[0].message.content.strip()
def retrieve_relevant_info(user_message: str):
    msg = user_message.lower()
    relevant_dosen = []
    keywords = msg.split()
    for item in dataset_dosen_data.get("data_dosen", []):
        nama_dosen = item.get("nama_dosen", "").lower()
        nip = item.get("nip", "")
        score = 0
        for keyword in keywords:
            keyword_score = fuzz.partial_ratio(keyword, nama_dosen)
            if keyword_score > 70:
                score += keyword_score
        if nip.lower() in msg or score > 100:
            relevant_dosen.append({
                "nama": item.get("nama_dosen", ""),
                "nip": nip,
                "score": score if nip.lower() not in msg else 1000
            })
    if not relevant_dosen:
        return "Tidak ada informasi dosen yang relevan ditemukan."
    relevant_dosen.sort(key=lambda x: x["score"], reverse=True)
    context = "Informasi dosen yang relevan:\n"
    for dosen in relevant_dosen:
        context += f"- Nama: {dosen['nama']}, NIP: {dosen['nip']}\n"
    context += "\n"
    return context
# ---------------- Helpers ---------------- #
def verify_password(input_password, stored_hash):
    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(input_password.encode("utf-8"), stored_hash)
    except ValueError:
        return False
jawaban_variasi = [
    "NIP dari {dosen} itu adalah {nip}",
    "NIP {nip} itu punya {dosen}",
    "{dosen} punya NIP: {nip}"
]
def get_jawaban(dosen, nip):
    template = random.choice(jawaban_variasi)
    return template.format(dosen=dosen, nip=nip)
# ---------------- Routes ---------------- #
@app.route("/")
def index():
    return send_from_directory("static", "index.html")
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message", "")
    save_question()
    try:
        reply = handle_zhipu_ai_with_rag(user_message)
    except Exception as e:
        print("⚠ Error di API:", e)
        reply = "⚠️ Maaf, server chatbot lagi error. Coba lagi nanti ya."
    return jsonify({"reply": reply})
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == ADMIN_USERNAME and verify_password(password, ADMIN_HASHED_PASSWORD):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Login gagal! Username atau password salah.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    create_table_if_not_exists()
    today_question_count = get_today_question_count()
    zhipu_connected = check_api_connection()
    return render_template(
        "dashboard.html",
        question_count=today_question_count,
        now=datetime.now(),
        dataset_dosen_data=dataset_dosen_data,
        zhipu_connected=zhipu_connected
    )
@app.route("/monitoring_faq")
def monitoring_faq():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    faq_data = [
        {"pertanyaan": "Siapa rektor UNDIP sekarang?", "jumlah": 5},
        {"pertanyaan": "Berapa NIP Prof. Wahyu Setia Budi?", "jumlah": 3},
        {"pertanyaan": "Bagaimana cara login ke SIA?", "jumlah": 7},
    ]
    return render_template("monitoring_faq.html", faq_data=faq_data)
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    flash("Change password disabled. Gunakan hash di .env", "info")
    return redirect(url_for("dashboard"))
@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))
@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))
@app.route("/get_questions_today")
def get_questions_today():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    count = get_today_question_count()
    return jsonify({"today_question_count": count})
if __name__ == "__main__":
    app.run(debug=True)