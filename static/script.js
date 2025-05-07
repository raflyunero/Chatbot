function handleKey(event) {
    if (event.key === "Enter") sendMessage();
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
        botMsg.textContent = data.reply;
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
    botMsg.textContent = "Hai DIPS, ada yang bisa saya bantu?";
    chatBody.appendChild(botMsg);
  }
    
  window.onload = clearChat;
  