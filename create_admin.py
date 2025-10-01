import bcrypt
from werkzeug.security import generate_password_hash
print(generate_password_hash("BORIGANTENG"))
import sqlite3

# Data admin
username = 'admin'
password = 'BORIGANTENG'

# Hash password dengan bcrypt
hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Connect ke SQLite
conn = sqlite3.connect("C:\\Chatbot\\database_chatbot.db")
cursor = conn.cursor()

# Buat tabel admin jika belum ada
cursor.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

# Hapus data lama dengan username yang sama (jika ada)
cursor.execute("DELETE FROM admin WHERE username = ?", (username,))

# Insert admin baru
cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", (username, hashed_password))

conn.commit()
conn.close()

print(f"✅ Admin '{username}' berhasil dibuat dengan password yang sudah di-hash bcrypt!")
