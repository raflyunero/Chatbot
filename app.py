from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session, render_template, flash
from flask_cors import CORS
from dotenv import load_dotenv
import bcrypt
import os
from datetime import datetime, timedelta
import sqlite3
import json
import random
from fuzzywuzzy import fuzz
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.embeddings.base import Embeddings
import re
import requests
import glob

# Import Zhipu AI
from zai import ZhipuAiClient

# ---------------- Setup Flask App ---------------- #
app = Flask(__name__, static_folder="static", static_url_path='')
CORS(app)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "default_secret")
app.permanent_session_lifetime = timedelta(hours=2)

# ---------------- Credentials & API ---------------- #
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_HASHED_PASSWORD = os.getenv("ADMIN_HASHED_PASSWORD", "").encode("utf-8")

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
client = ZhipuAiClient(api_key=ZHIPU_API_KEY)

# ---------------- Helpers ---------------- #
def verify_password(input_password, stored_hash):
    return bcrypt.checkpw(input_password.encode('utf-8'), stored_hash)


def get_jawaban(dosen, nip):
    template = random.choice(jawaban_variasi)
    return template.format(dosen=dosen, nip=nip)


jawaban_variasi = [
    "NIP dari {dosen} itu adalah {nip}",
    "NIP {nip} itu punya {dosen}",
    "{dosen} punya NIP: {nip}"
]


# ---------------- Dataset Handlers ---------------- #
def get_undip_response(user_message: str):
    reply = retrieve_relevant_info(user_message)
    if reply:
        return reply
    return handle_zhipu_ai_with_rag(user_message)

# ---------------- Load Dataset JSON (dosen) ---------------- #
dataset_dosen_data = {}
try:
    with open("dataset_dosen.json", "r", encoding="utf-8") as f:
        dataset_dosen_data = json.load(f)
except Exception as e:
    print("⚠️ Gagal load dataset_dosen.json:", e)

# ---------------- Database Setup ---------------- #
def get_db():
    return sqlite3.connect('questions.db')

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
    conn.close()
    return row[0] if row else 0

# ---------------- Zhipu AI Embeddings Class (FIXED) ---------------- #
class ZhipuEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str = "embedding-2"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/embeddings"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed banyak dokumen, kirim satu per satu biar tidak error 400"""
        embeddings = []
        for text in texts:
            data = {
                "model": self.model,
                "input": text
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            try:
                response = requests.post(self.base_url, headers=headers, json=data)
                if response.status_code != 200:
                    print("⚠️ Zhipu embedding error:", response.text)
                    continue
                result = response.json()
                embeddings.append(result["data"][0]["embedding"])
            except Exception as e:
                print("⚠️ Error embed text:", e)
                continue
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed satu query"""
        data = {
            "model": self.model,
            "input": text
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(self.base_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["data"][0]["embedding"]

# ---------------- PDF Processing ---------------- #
def clean_pdf_text(text):
    text = re.sub(r'[^\w\s\.\,\-\:\(\)\@]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def init_pdf_vectorstore_from_folder(folder_path):
    try:
        all_documents = []
        pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {folder_path}")
            return None
            
        print(f"Found {len(pdf_files)} PDF files to process")
        
        for pdf_file in pdf_files:
            print(f"Processing {pdf_file}...")
            loader = PyPDFLoader(pdf_file)
            documents = loader.load()
            
            # Clean text
            for doc in documents:
                doc.page_content = clean_pdf_text(doc.page_content)
            
            all_documents.extend(documents)
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,   # lebih kecil biar aman
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", " "]
        )
        texts = text_splitter.split_documents(all_documents)
        
        # Use Zhipu AI Embeddings
        embeddings = ZhipuEmbeddings(api_key=ZHIPU_API_KEY)
        vectorstore = FAISS.from_documents(texts, embeddings)
        
        return vectorstore
    except Exception as e:
        print(f"Error processing PDFs: {e}")
        return None

def retrieve_from_pdf(query: str, k=3):
    if pdf_vectorstore is None:
        return ""
    docs = pdf_vectorstore.similarity_search(query, k=k)
    return "\n".join([doc.page_content for doc in docs])

# Initialize PDF vectorstore from folder
pdf_vectorstore = None
pdf_folder = "pdfs"  # Folder containing PDF files

# Create folder if it doesn't exist
if not os.path.exists(pdf_folder):
    os.makedirs(pdf_folder)
    print(f"Created folder: {pdf_folder}")

pdf_vectorstore = init_pdf_vectorstore_from_folder(pdf_folder)
if pdf_vectorstore:
    print("✅ PDFs processed successfully!")
else:
    print("⚠️ No PDFs found or error processing PDFs. RAG functionality will be limited.")

# ---------------- RAG -------------------- #
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
                "Kamu adalah chatbot akademik Universitas Diponegoro (UNDIP). "
                "Jawablah dengan bahasa santai, sopan, dan jelas ala anak muda 🤙, "
                "tetap fokus pada konteks akademik."
            )},
            {"role": "user", "content": augmented_prompt}
        ]
    )
    return response.choices[0].message.content.strip()


def retrieve_relevant_info(user_message: str):
    context = ""
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

    if relevant_dosen:
        relevant_dosen.sort(key=lambda x: x["score"], reverse=True)
        context += "Informasi dosen yang relevan:\n"
        for dosen in relevant_dosen:
            context += f"- Nama: {dosen['nama']}, NIP: {dosen['nip']}\n"
    else:
        context += "Tidak ada informasi dosen yang relevan ditemukan.\n"

    if pdf_vectorstore is not None:
        pdf_context = retrieve_from_pdf(user_message)
        if pdf_context.strip():
            context += "\n\nInformasi dari dokumen:\n"
            context += pdf_context

    return context

# ---------------- Routes ---------------- #
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message", "")
    save_question()
    reply = handle_zhipu_ai_with_rag(user_message)
    return jsonify({"reply": reply})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == ADMIN_USERNAME and verify_password(password, ADMIN_HASHED_PASSWORD):
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
    return render_template("admin_panel.html", question_count=today_question_count)

# ---------------- Main ---------------- #
if __name__ == "__main__":
    app.run(debug=True)
