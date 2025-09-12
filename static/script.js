function handleKey(event) {
    if (event.key === "Enter") sendMessage();
}

// Fungsi untuk ubah markdown menjadi HTML (bold + list)
function markdownToHTML(text) {
    // Bold **text**
    let html = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');

    // Ubah angka urut menjadi <ol><li>
    // Contoh: "1. Fakultas Hukum" menjadi list
    let lines = html.split(/\n|(?=\d+\.\s)/g); // pecah per baris / nomor
    let olStarted = false;
    let newLines = [];

    lines.forEach(line => {
        if (/^\d+\.\s/.test(line)) { // jika diawali angka
            if (!olStarted) {
                newLines.push('<ol>');
                olStarted = true;
            }
            let liText = line.replace(/^\d+\.\s*/, '');
            newLines.push(`<li>${liText}</li>`);
        } else {
            if (olStarted) {
                newLines.push('</ol>');
                olStarted = false;
            }
            newLines.push(line);
        }
    });
    if (olStarted) newLines.push('</ol>');

    return newLines.join('');
}

async function sendMessage() {
    const input = document.getElementById("userInput");
    const message = input.value.trim();
    if (!message) return;

    const chatBody = document.getElementById("chatBody");

    const userMsg = document.createElement("div");
    userMsg.className = "message user-message";
    userMsg.textContent = message;
    chatBody.appendChild(userMsg);

    input.value = "";

    const typingMsg = document.createElement("div");
    typingMsg.className = "message typing-message";
    typingMsg.textContent = "Mengetik...";
    chatBody.appendChild(typingMsg);
    chatBody.scrollTop = chatBody.scrollHeight;

    setTimeout(async () => {
        try {
            const res = await fetch("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message })
            });
            const data = await res.json();

            typingMsg.remove();

            const botMsg = document.createElement("div");
            botMsg.className = "message bot-message";
            botMsg.innerHTML = markdownToHTML(data.reply);
            chatBody.appendChild(botMsg);
            chatBody.scrollTop = chatBody.scrollHeight; 
        } catch {
            typingMsg.remove();
            const botMsg = document.createElement("div");
            botMsg.className = "message bot-message";
            botMsg.textContent = "Terjadi kesalahan pada server.";
            chatBody.appendChild(botMsg);
            chatBody.scrollTop = chatBody.scrollHeight; 
        }
    }, 1000); 
}

function clearChat() {
    const chatBody = document.getElementById("chatBody");
    chatBody.innerHTML = "";

    const botMsg = document.createElement("div");
    botMsg.className = "message bot-message";
    botMsg.innerHTML = "Hai DIPS, ada yang bisa saya bantu?";
    botMessage.innerHTML = response.reply;
    chatBody.appendChild(botMsg);
    chatBody.scrollTop = chatBody.scrollHeight; 
}

window.onload = clearChat;
