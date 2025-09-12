import json

# Load data JSON
with open("undip_program_sarjana.json", "r", encoding="utf-8") as f:
    program_data = json.load(f)

print("Chatbot Akademik UNDIP")
print("Ketik 'exit' untuk keluar.\n")

while True:
    user_input = input("Kamu: ").strip().lower()

    if user_input == "exit":
        print("Chatbot: Sampai jumpa!")
        break

    response_found = False

    # Cek apakah user menyebut nama fakultas
    for fakultas, prodi_list in program_data.items():
        if fakultas.lower() in user_input:
            response_found = True
            print(f"Chatbot: Program studi di {fakultas}:")
            for prodi in prodi_list:
                print(f" - {prodi}")
            break

    if not response_found:
        print("Chatbot: Maaf, saya tidak mengerti. Coba sebutkan nama fakultas yang ada.")
