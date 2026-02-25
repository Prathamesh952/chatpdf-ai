const API = "https://chatpdf-ai.onrender.com";
// ← Change to your Render URL after deploying

let currentPDF = "";
let sessionID = null;

const messages = document.getElementById("messages");
const loader = document.getElementById("loader");
const fileInput = document.getElementById("fileInput");
const welcome = document.querySelector(".welcome");
const historyBox = document.getElementById("history");

/* =========================
   LOADER
========================= */
function showLoader() { loader.classList.add("active"); }

function hideLoader() { loader.classList.remove("active"); }

/* =========================
   MESSAGE HELPERS
========================= */
function add(type, text) {
    const d = document.createElement("div");
    d.className = "msg " + type;
    d.innerHTML = type === "ai" ? marked.parse(text) : text;
    messages.appendChild(d);
    messages.scrollTop = messages.scrollHeight;
}

function typeAI(text) {
    let i = 0;
    const d = document.createElement("div");
    d.className = "msg ai";
    messages.appendChild(d);

    const timer = setInterval(() => {
        d.innerHTML = marked.parse(text.slice(0, i++));
        messages.scrollTop = messages.scrollHeight;
        if (i > text.length) clearInterval(timer);
    }, 10);
}

/* =========================
   PDF UPLOAD
========================= */
fileInput.addEventListener("change", async (e) => {

    const file = e.target.files[0];
    if (!file) return;

    currentPDF = file.name;
    showLoader();

    const reader = new FileReader();

    reader.onload = async () => {
        const base64 = reader.result.split(",")[1];

        // 1️⃣ Upload PDF
        const res = await fetch(`${API}/process-pdf`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                pdf_data: base64,
                pdf_id: file.name
            })
        });

        const data = await res.json();
        if (!res.ok) {
            hideLoader();
            alert("❌ " + (data.error || "Upload failed"));
            return;
        }

        // 2️⃣ Create session for this PDF
        const chatRes = await fetch(`${API}/new-chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pdf_id: file.name })
        });

        const chatData = await chatRes.json();
        sessionID = chatData.session_id;

        // hide welcome screen
        welcome.style.display = "none";

        // clear chat
        messages.innerHTML = "";
        add("ai", `✅ PDF processed (${data.chunks} chunks indexed). Ask anything from it.`);

        // show history entry
        addHistoryItem(file.name, sessionID);

        hideLoader();
    };

    reader.readAsDataURL(file);
});

/* =========================
   ASK QUESTION
========================= */
async function ask() {

    if (!sessionID) return alert("Upload PDF first");

    const input = document.getElementById("question");
    const q = input.value.trim();
    if (!q) return;

    add("user", q);
    input.value = "";
    showLoader();

    const res = await fetch(`${API}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            question: q,
            session_id: sessionID
        })
    });

    const data = await res.json();
    hideLoader();
    typeAI(data.answer || "No answer.");
}

/* =========================
   NEW CHAT
========================= */
async function newChat() {

    if (!currentPDF) {
        alert("Upload PDF first");
        return;
    }

    const res = await fetch(`${API}/new-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf_id: currentPDF })
    });

    const data = await res.json();
    sessionID = data.session_id;

    messages.innerHTML = "";
    add("ai", "🆕 New chat started. Ask your questions.");

    addHistoryItem(currentPDF, sessionID);
}

/* =========================
   LOAD HISTORY FROM BACKEND
========================= */
async function loadHistory(id) {

    sessionID = id;
    messages.innerHTML = "";
    showLoader();

    const res = await fetch(`${API}/history`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: id })
    });

    const history = await res.json();
    hideLoader();

    history.forEach(m => add(m.role, m.text));
}

/* =========================
   ADD HISTORY ITEM IN SIDEBAR
========================= */
function addHistoryItem(name, id) {

    const d = document.createElement("div");
    d.style.cursor = "pointer";
    d.style.padding = "6px";
    d.textContent = name;

    d.onclick = () => loadHistory(id);

    historyBox.prepend(d);
}

/* EXPORTS */
window.ask = ask;
window.newChat = newChat;