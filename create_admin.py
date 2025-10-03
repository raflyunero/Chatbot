import bcrypt

# Data admin
username = 'admin'
password = 'BORIGANTENG'

# Hash password dengan bcrypt (tetap dalam bytes)
hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(f"✅ Admin '{username}' berhasil dibuat dengan password yang sudah di-hash bcrypt!")

# Debug info
print("Input password:", password)
print("Stored hash:", hashed_password.decode('utf-8'))  # decode cuma untuk ditampilkan

# Cek password
is_correct = bcrypt.checkpw(password.encode('utf-8'), hashed_password)
print("Check:", is_correct)  # Harus True
