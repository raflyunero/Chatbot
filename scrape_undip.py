from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json

options = Options()
options.add_argument("--start-maximized")
# options.add_argument("--headless")  # uncomment jika ingin headless

driver = webdriver.Chrome(service=Service(), options=options)
driver.get("https://undip.ac.id/program-sarjana-2")
print("Halaman berhasil dibuka!")

wait = WebDriverWait(driver, 30)  # tunggu maksimal 20 detik

program_data = {}

# Ambil semua container fakultas
containers = driver.find_elements(By.CSS_SELECTOR, ".elementor-widget-container")

for container in containers:
    try:
        fakultas_name = container.find_element(By.TAG_NAME, "h3").text.strip()
        
        # Tunggu ul dengan li muncul dalam container
        ul = wait.until(EC.presence_of_element_located(
            (By.XPATH, ".//ul[li]")))  # pastikan ada li di dalam ul

        prodi_list = [li.text.strip() for li in ul.find_elements(By.TAG_NAME, "li")]

        if fakultas_name and prodi_list:
            program_data[fakultas_name] = prodi_list
    except:
        continue

# Simpan ke JSON
with open("undip_program_sarjana.json", "w", encoding="utf-8") as f:
    json.dump(program_data, f, ensure_ascii=False, indent=4)

print("Data berhasil disimpan ke undip_program_sarjana.json!")
driver.quit()
