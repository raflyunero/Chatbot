from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template, flash
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import openai
import os
from datetime import datetime
import sqlite3

# Setup Flask app
app = Flask(__name__, static_folder="static", static_url_path='')
CORS(app)

# Load environment variables
load_dotenv()

# Admin credentials (from .env file)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Kunci API OpenAI (diambil dari environment variables)
api_key = os.getenv("OPENAI_API_KEY")
openai.api_key = api_key

# Hashing password default untuk admin
hashed_password = bcrypt.hashpw("BORIGANTENG".encode('utf-8'), bcrypt.gensalt())

# Database connection (untuk jumlah pertanyaan hari ini)
def get_db():
    conn = sqlite3.connect('questions.db')
    return conn

# Fungsi untuk memastikan tabel 'question_count' ada
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

# Fungsi untuk menyimpan pertanyaan ke database
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

# Fungsi untuk mendapatkan jumlah pertanyaan hari ini
def get_today_question_count():
    conn = get_db()
    cursor = conn.cursor()

    today = datetime.today().strftime('%Y-%m-%d')
    cursor.execute("SELECT count FROM question_count WHERE date = ?", (today,))
    row = cursor.fetchone()

    count = row[0] if row else 0
    print(f"Jumlah pertanyaan hari ini ({today}): {count}")  # Log jumlah pertanyaan
    conn.close()

    return count

# Fungsi untuk memverifikasi password
def verify_password(input_password, stored_hash):
    return bcrypt.checkpw(input_password.encode('utf-8'), stored_hash)

# Fungsi untuk membatasi topik hanya seputar UNDIP
def get_undip_response(user_message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-nano",  # atau model lainnya jika kamu punya akses
            messages=[{
                    "role": "system",
                    "content": ("Kamu adalah chatbot akademik Undip yang menjawab dengan bahasa santai, gaul, dan seperti anak muda zaman sekarang. Jawaban tetap sopan, singkat, jelas, dan tetap sesuai konteks akademik."
                        "Kamu adalah chatbot yang hanya menjawab pertanyaan tentang Universitas Diponegoro (UNDIP) dan beserta informasi di setiap fakultas seperti nama dosen, "
                        "termasuk fakultas, program studi, layanan akademik, jadwal kuliah, pendaftaran, beasiswa, dan sejenisnya. "
                        "Jika ada pertanyaan di luar topik UNDIP, tolak dengan sopan."
                    ),
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error:", e)
        return "Maaf, terjadi kesalahan saat menghubungi server."

# Route untuk halaman login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Cek apakah username dan password cocok
        if username == ADMIN_USERNAME and verify_password(password, hashed_password):
            session["logged_in"] = True
            return redirect(url_for("admin"))
        else:
            flash("Login gagal! Username atau password salah.", "error")  # Flash error message
            return redirect(url_for("login"))

    return render_template("login.html")

# Route untuk halaman logout
@app.route("/logout")
def logout():
    session.pop("logged_in", None)  # Menghapus sesi login
    return redirect(url_for("login"))  # Arahkan kembali ke halaman login

# Route untuk halaman utama
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# Route API untuk chatbot
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message", "")
    
    # Simpan pertanyaan ke database
    save_question()

    # Dapatkan balasan dari chatbot
    reply = get_undip_response(user_message)

    # Kirim balik balasan
    return jsonify({"reply": reply})

# Route untuk halaman dashboard admin
# Route untuk halaman dashboard admin
@app.route('/admin/dashboard')
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    # Pastikan tabel question_count ada
    create_table_if_not_exists()

    # Ambil jumlah pertanyaan hari ini
    today_question_count = get_today_question_count()

    # Render template dengan jumlah pertanyaan hari ini
    return render_template("admin_panel.html", question_count=today_question_count)

    return redirect(url_for("login"))
    
    # Ambil jumlah pertanyaan hari ini
@app.route("/get_questions_today", methods=["GET"])
def get_questions_today():
    today_question_count = get_today_question_count()
    return jsonify({"today_question_count": today_question_count})

    return render_template('dashboard.html', question_count=today_question_count)
# Fungsi untuk mendapatkan jumlah pertanyaan hari ini
def get_today_question_count():
    conn = get_db()
    cursor = conn.cursor()

    today = datetime.today().strftime('%Y-%m-%d')
    cursor.execute("SELECT count FROM question_count WHERE date = ?", (today,))
    row = cursor.fetchone()

    count = row[0] if row else 0
    print(f"Jumlah pertanyaan hari ini ({today}): {count}")  # Log jumlah pertanyaan
    conn.close()

    return count

# Route untuk halaman monitoring FAQ
@app.route('/admin/monitoring')
def monitoring_faq():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template('monitoring_faq.html')

# Route untuk halaman ganti password
@app.route('/admin/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validasi password lama dan kecocokan password baru
        if verify_password(old_password, hashed_password) and new_password == confirm_password:
            hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            flash("Password berhasil diubah!", "success")
            return redirect(url_for('admin'))
        else:
            flash("Password tidak sesuai atau tidak cocok!", "error")
    
    return render_template('change_password.html')

# Route untuk halaman admin utama
@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    # Pastikan tabel question_count ada
    create_table_if_not_exists()

    # Ambil jumlah pertanyaan hari ini
    today_question_count = get_today_question_count()

    return render_template("admin_panel.html", question_count=today_question_count)

# Run server
if __name__ == "__main__":
    app.secret_key = os.getenv("OPENAI_API_KEY")
    app.run(debug=True)
