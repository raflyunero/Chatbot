import requests
from bs4 import BeautifulSoup
import json

url = "https://ft.undip.ac.id/program-studi/"
res = requests.get(url)
soup = BeautifulSoup(res.text, "html.parser")

# Ambil daftar program studi dari halaman
prodi_list = []

# Sesuaikan selector dengan HTML terbaru
for li in soup.select("div.entry-content ul li"):
    prodi_list.append(li.text.strip())

# Simpan ke JSON
with open("ft_prodi.json", "w", encoding="utf-8") as f:
    json.dump(prodi_list, f, ensure_ascii=False, indent=4)

print("Dataset tersimpan di ft_prodi.json")
