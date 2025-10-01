from flask import (
    Flask, request, jsonify, send_from_directory,
    redirect, url_for, session, render_template,
    flash, make_response
)
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import os, sqlite3, json, random, string
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Import Zhipu AI (pastikan library zai terpasang / client tersedia)
from zai import ZhipuAiClient

# ---------------- Setup Flask App ---------------- #
app = Flask(__name__, static_folder="static", static_url_path='')
CORS(app)
load_dotenv()
# pakai SECRET_KEY dari .env jika ada, kalau tidak generate sementara
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(24)
app.permanent_session_lifetime = timedelta(hours=2)

# ---------------- API Key Zhipu ---------------- #
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
client = ZhipuAiClient(api_key=ZHIPU_API_KEY) if ZHIPU_API_KEY else None

# ---------------- Dataset Dosen Functions ---------------- #
def load_dataset_dosen():
    """Fungsi untuk memuat dataset dosen dari file JSON"""
    global dataset_dosen_data
    try:
        with open("dataset_dosen.json", "r", encoding="utf-8") as f:
            dataset_dosen_data = json.load(f)
        print("✅ Dataset dosen berhasil dimuat")
        return True
    except FileNotFoundError:
        print("❌ File dataset_dosen.json tidak ditemukan")
        dataset_dosen_data = {}
        return False
    except json.JSONDecodeError:
        print("❌ Error parsing JSON dari dataset_dosen.json")
        dataset_dosen_data = {}
        return False
    except Exception as e:
        print(f"❌ Gagal load dataset_dosen.json: {e}")
        dataset_dosen_data = {}
        return False

def get_dataset_dosen_status():
    """Fungsi untuk mendapatkan status dataset dosen"""
    if not dataset_dosen_data:
        return {
            "status": "not_loaded",
            "message": "Dataset dosen tidak tersedia",
            "count": 0
        }
    
    data_count = len(dataset_dosen_data.get("data_dosen", []))
    return {
        "status": "loaded",
        "message": "Dataset dosen berhasil dimuat",
        "count": data_count,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ---------------- Dataset Rektor Functions ---------------- #
def load_dataset_rektor():
    """Fungsi untuk memuat dataset rektor dari file JSON"""
    global dataset_rektor_data
    try:
        with open("dataset_rektor.json", "r", encoding="utf-8") as f:
            dataset_rektor_data = json.load(f)
        print("✅ Dataset rektor berhasil dimuat")
        return True
    except FileNotFoundError:
        print("❌ File dataset_rektor.json tidak ditemukan")
        dataset_rektor_data = []
        return False
    except json.JSONDecodeError:
        print("❌ Error parsing JSON dari dataset_rektor.json")
        dataset_rektor_data = []
        return False
    except Exception as e:
        print(f"❌ Gagal load dataset_rektor.json: {e}")
        dataset_rektor_data = []
        return False

def get_dataset_rektor_status():
    """Fungsi untuk mendapatkan status dataset rektor"""
    if not dataset_rektor_data:
        return {
            "status": "not_loaded",
            "message": "Dataset rektor tidak tersedia",
            "count": 0
        }
    
    data_count = len(dataset_rektor_data)
    return {
        "status": "loaded",
        "message": "Dataset rektor berhasil dimuat",
        "count": data_count,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ---------------- Load Dataset JSON ---------------- #
dataset_dosen_data = {}
dataset_rektor_data = []
load_dataset_dosen()
load_dataset_rektor()

# ---------------- Database Setup ---------------- #
def get_questions_db():
    return sqlite3.connect('questions.db')

def create_table_if_not_exists():
    conn = get_questions_db()
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
    conn = get_questions_db()
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
    conn = get_questions_db()
    cursor = conn.cursor()
    today = datetime.today().strftime('%Y-%m-%d')
    cursor.execute("SELECT count FROM question_count WHERE date = ?", (today,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

# ---------------- Helpers ---------------- #
def verify_password(input_password, stored_hash):
    """
    stored_hash is expected to be a plaintext string from DB (bcrypt hash like "$2b$12$...")
    """
    try:
        return bcrypt.checkpw(input_password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        return False

def get_jawaban(dosen, nip):
    template = random.choice(jawaban_variasi)
    return template.format(dosen=dosen, nip=nip)

jawaban_variasi = [
    "NIP dari {dosen} itu adalah {nip}",
    "NIP {nip} itu punya {dosen}",
    "{dosen} punya NIP: {nip}"
]

def get_jawaban_rektor(nama, periode, keterangan):
    template = random.choice(jawaban_rektor_variasi)
    return template.format(nama=nama, periode=periode, keterangan=keterangan)

jawaban_rektor_variasi = [
    "{nama} menjabat sebagai Rektor UNDIP pada periode {periode}. {keterangan}",
    "Periode {periode}, Rektor UNDIP dijabat oleh {nama}. {keterangan}",
    "{nama} adalah Rektor UNDIP periode {periode}. {keterangan}"
]

# ---------------- Dataset Handlers ---------------- #
def handle_dataset_dosen(message: str):
    msg = message.lower()

    # hanya periksa dataset kalau relevan
    if not ("nip" in msg or "dosen" in msg):
        return None

    # Cek apakah dataset tersedia
    if not dataset_dosen_data or "data_dosen" not in dataset_dosen_data:
        return "⚠️ Data dosen tidak tersedia saat ini. Silakan hubungi admin."

    best_match = None
    best_score = 0

    for item in dataset_dosen_data.get("data_dosen", []):
        nama_dosen = item.get("nama_dosen", "").lower()
        nip = item.get("nip", "")

        # fuzzy match
        score = fuzz.partial_ratio(msg, nama_dosen)
        # debug: print(nama_dosen, score)

        if score > 75 and score > best_score:
            best_score = score
            best_match = (item.get("nama_dosen", ""), nip)

        # cek kalau NIP disebutkan langsung
        if nip and nip.lower() in msg:
            return get_jawaban(item.get("nama_dosen", ""), nip)

    if best_match:
        return get_jawaban(best_match[0], best_match[1])

    return None

def handle_dataset_rektor(message: str):
    msg = message.lower()
    
    # hanya periksa dataset kalau relevan
    rektor_keywords = ["rektor", "pimpinan", "kepala", "pemimpin"]
    if not any(keyword in msg for keyword in rektor_keywords):
        return None

    # Cek apakah dataset tersedia
    if not dataset_rektor_data:
        return "⚠️ Data rektor tidak tersedia saat ini. Silakan hubungi admin."

    best_match = None
    best_score = 0

    # Cek untuk pertanyaan tentang rektor sekarang
    if "sekarang" in msg or "saat ini" in msg or "current" in msg:
        # Cari rektor dengan periode terbaru yang mengandung tahun sekarang atau masa depan
        current_year = datetime.now().year
        for item in dataset_rektor_data:
            periode = item.get("periode", "")
            nama = item.get("nama", "")
            keterangan = item.get("keterangan", "")
            
            # Cek jika periode mengandung tahun sekarang atau kata "sekarang" di keterangan
            if (str(current_year) in periode or 
                "sekarang" in keterangan.lower() or 
                "2024–2029" in periode or  # Periode terbaru yang kita tahu
                "2024-2029" in periode):
                # Set flag di session bahwa kita baru saja menjawab pertanyaan rektor
                session['just_answered_rektor'] = True
                return get_jawaban_rektor(nama, periode, keterangan)

    for item in dataset_rektor_data:
        nama_rektor = item.get("nama", "").lower()
        periode = item.get("periode", "")
        keterangan = item.get("keterangan", "")

        # fuzzy match untuk nama rektor
        score_nama = fuzz.partial_ratio(msg, nama_rektor)
        
        # cek periode
        score_periode = 0
        if periode.lower() in msg:
            score_periode = 90
        
        # ambil score tertinggi antara nama dan periode
        score = max(score_nama, score_periode)

        if score > 70 and score > best_score:
            best_score = score
            best_match = (item.get("nama", ""), periode, keterangan)

    if best_match:
        # Set flag di session bahwa kita baru saja menjawab pertanyaan rektor
        session['just_answered_rektor'] = True
        return get_jawaban_rektor(best_match[0], best_match[1], best_match[2])

    # Jika pertanyaan tentang rektor tapi tidak ada kecocokan
    return "Maaf, informasi tentang rektor yang Anda tanyakan tidak ditemukan dalam database kami."

def handle_zhipu_ai(user_message: str):
    if client is None:
        return "⚠️ AI service tidak tersedia. Coba lagi nanti."
    try:
        response = client.chat.completions.create(
            model="glm-4.5",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Lo sekarang jadi chatbot akademik Universitas Diponegoro (UNDIP). "
                        "Jawaban lo wajib pake bahasa santai, gaul, ala anak muda jaman sekarang 🤙, "
                        "tapi tetep sopan, singkat, jelas, dan gak keluar konteks akademik."
                    ),
                },
                {"role": "user", "content": user_message}
            ],
            thinking={"type": "enabled"},
            max_tokens=800,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Error Zhipu:", e)
        return "⚠️ Maaf bro, ada error pas kita ngehubungin Server🙏"

def get_undip_response(user_message: str):
    msg = user_message.lower()

    # 1. Cek dataset rektor dulu
    if any(keyword in msg for keyword in ["rektor", "pimpinan", "kepala", "pemimpin"]):
        rektor_reply = handle_dataset_rektor(user_message)
        if rektor_reply and "tidak ditemukan" not in rektor_reply.lower():
            return rektor_reply
        # kalau tidak ketemu, baru lanjut ke AI
        return handle_zhipu_ai(user_message)

    # 2. Kalau bukan rektor, cek dataset dosen
    if "dosen" in msg or "nip" in msg:
        dosen_reply = handle_dataset_dosen(user_message)
        if dosen_reply:
            return dosen_reply
        # kalau tidak ketemu, lanjut ke AI
        return handle_zhipu_ai(user_message)

    # 3. Kalau bukan rektor / dosen → langsung pakai AI
    return handle_zhipu_ai(user_message)

# ---------------- CAPTCHA ---------------- #
def random_text(length=5):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_captcha_image(text):
    width, height = 200, 70
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 38)
    except Exception:
        font = ImageFont.load_default()

    # garis noise
    for _ in range(8):
        start = (random.randint(0, width), random.randint(0, height))
        end = (random.randint(0, width), random.randint(0, height))
        draw.line([start, end], fill=(random.randint(100,200), random.randint(100,200), random.randint(100,200)), width=2)

    # huruf dengan rotasi
    for i, ch in enumerate(text):
        char_img = Image.new('RGBA', (50, 60), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((5, 5), ch, font=font, fill=(0, 0, 0))
        rotated = char_img.rotate(random.randint(-25, 25), expand=1, fillcolor=(255,255,255))
        x = 20 + i * 30 + random.randint(-5, 5)
        y = random.randint(0, 10)
        image.paste(rotated, (x, y), rotated)

    # titik noise
    for _ in range(250):
        x = random.randint(0, width-1)
        y = random.randint(0, height-1)
        draw.point((x, y), fill=(random.randint(0,255), random.randint(0,255), random.randint(0,255)))

    image = image.filter(ImageFilter.SMOOTH)
    return image

# ---------------- Routes: CAPTCHA flow ---------------- #
@app.route("/")
def show_captcha_page():
    """
    Root halaman: tampilkan halaman captcha_page.html (file harus ada di templates/)
    """
    return render_template("captcha_page.html")

@app.route("/captcha.png")
def captcha_png():
    text = random_text(5)
    session['captcha_text'] = text
    image = generate_captcha_image(text)
    buf = BytesIO()
    image.save(buf, 'PNG')
    buf.seek(0)
    response = make_response(buf.read())
    response.headers['Content-Type'] = 'image/png'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route("/submit_captcha", methods=["POST"])
def submit_captcha():
    user_answer = request.form.get("captcha", "").strip()
    real = session.get("captcha_text", "")
    session.pop("captcha_text", None)

    if user_answer and real and user_answer == real:
        # tandai user sudah melewati captcha untuk sesi ini
        session['passed_captcha'] = True
        return redirect(url_for("main_app"))
    else:
        flash("CAPTCHA salah — coba lagi.", "error")
        return render_template("captcha_page.html")

@app.route("/main")
def main_app():
    # Hanya boleh diakses kalau user sudah melewati captcha
    if not session.get('passed_captcha'):
        return redirect(url_for("show_captcha_page"))
    # tampilkan frontend chatbot
    return send_from_directory("static", "index.html")

# ---------------- Routes: Chatbot API ---------------- #
@app.route("/ask", methods=["POST", "OPTIONS"])
def ask():
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"})
    
    # pastikan user melewati captcha dulu
    if not session.get('passed_captcha'):
        return jsonify({"reply": "Silakan lewati CAPTCHA di root (/) dulu."}), 403

    data = request.get_json() or {}
    user_message = data.get("message", "")
    save_question()
    reply = get_undip_response(user_message)
    return jsonify({"reply": reply})

# ---------------- Routes: Dataset Management (Admin Only) ---------------- #
@app.route("/admin/reload_dataset_dosen", methods=["POST"])
def reload_dataset_dosen():
    """Endpoint untuk memuat ulang dataset dosen (hanya admin)"""
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
    
    success = load_dataset_dosen()
    if success:
        return jsonify({
            "success": True, 
            "message": "Dataset dosen berhasil dimuat ulang",
            "status": get_dataset_dosen_status()
        })
    else:
        return jsonify({
            "success": False, 
            "message": "Gagal memuat dataset dosen"
        }), 500

@app.route("/admin/reload_dataset_rektor", methods=["POST"])
def reload_dataset_rektor():
    """Endpoint untuk memuat ulang dataset rektor (hanya admin)"""
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
    
    success = load_dataset_rektor()
    if success:
        return jsonify({
            "success": True, 
            "message": "Dataset rektor berhasil dimuat ulang",
            "status": get_dataset_rektor_status()
        })
    else:
        return jsonify({
            "success": False, 
            "message": "Gagal memuat dataset rektor"
        }), 500

@app.route("/admin/dataset_dosen_status")
def dataset_dosen_status():
    """Endpoint untuk melihat status dataset dosen (hanya admin)"""
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
    
    return jsonify(get_dataset_dosen_status())

@app.route("/admin/dataset_rektor_status")
def dataset_rektor_status():
    """Endpoint untuk melihat status dataset rektor (hanya admin)"""
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
    
    return jsonify(get_dataset_rektor_status())

# ---------------- Routes: Admin (login requires captcha passed) ---------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    # user harus melewati captcha sebelum ke login
    if not session.get('passed_captcha'):
        return redirect(url_for("show_captcha_page"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        conn = sqlite3.connect("C:\\Chatbot\\database_chatbot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM admin WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row and verify_password(password, row[0]):
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

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    create_table_if_not_exists()
    today_question_count = get_today_question_count()
    dataset_dosen_info = get_dataset_dosen_status()
    dataset_rektor_info = get_dataset_rektor_status()
    return render_template("admin_panel.html", 
                          question_count=today_question_count,
                          dataset_dosen_status=dataset_dosen_info,
                          dataset_rektor_status=dataset_rektor_info)

# ---------------- Run App ---------------- #
if __name__ == "__main__":
    # Pastikan templates: captcha_page.html, login.html, admin_panel.html ada di templates/
    # Pastikan static/index.html ada untuk main app
    app.run(debug=True)
