from flask import Flask, request
from flask_cors import CORS
import pdfplumber, io, base64, json, os, math, requests, uuid
import platform

# Tesseract — cross-platform path
try:
    import pytesseract
    from PIL import Image
    if platform.system() == "Windows":
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False

from groq import Groq

app = Flask(__name__)
from flask_cors import CORS

CORS(app, resources={
    r"/*": {
        "origins": [
            "https://chatwithpdfai.netlify.app",
            "http://localhost:5500",
            "http://127.0.0.1:5500"
        ]
    }
})
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # ~500MB

# =========================
# ENV / API KEYS
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HF_API_KEY   = os.getenv("HF_API_KEY", "")        # HuggingFace — optional but improves rate limits

# =========================
# STORAGE
# =========================
os.makedirs("storage", exist_ok=True)

DOC_FILE  = "storage/documents.json"
CHAT_FILE = "storage/chat_history.json"
DOC_CACHE = None
MAX_CHUNKS_PER_PDF = 20000


# =========================
# JSON HELPERS
# =========================
def load_json(path, default):
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_doc_cache():
    global DOC_CACHE
    DOC_CACHE = load_json(DOC_FILE, {"chunks": []})


# =========================
# RAG HELPERS
# =========================
def chunk_text(text, size=180, overlap=40):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        c = " ".join(words[i:i+size])
        if len(c.strip()) > 40:
            chunks.append(c)
        i += size - overlap
    return chunks


def cosine(a, b):
    if not a or not b:
        return 0
    dot = sum(x*y for x, y in zip(a, b))
    ma = math.sqrt(sum(x*x for x in a))
    mb = math.sqrt(sum(x*x for x in b))
    return dot / (ma * mb) if ma and mb else 0


# ----- FREE EMBEDDINGS via HuggingFace Inference API -----
HF_EMBED_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

def hf_embed(text):
    """Generate embeddings using HuggingFace free Inference API."""
    headers = {}
    if HF_API_KEY:
        headers["Authorization"] = f"Bearer {HF_API_KEY}"
    try:
        r = requests.post(
            HF_EMBED_URL,
            headers=headers,
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=60
        )
        result = r.json()
        # API returns list of floats OR list of list of floats
        if isinstance(result, list):
            if isinstance(result[0], float):
                return result
            elif isinstance(result[0], list):
                return result[0]
        return []
    except Exception as e:
        print("HF embed error:", e)
        return []


# ----- FREE LLM via Groq API -----
def generate(prompt):
    """Generate answer using Groq's free LLM API (Llama 3)."""
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not set."
    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=512,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("Groq error:", e)
        return "Answer is not present in the PDF."


# =========================
# ROUTES
# =========================
@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/new-chat", methods=["POST"])
def new_chat():
    pdf_id = request.json.get("pdf_id")
    chats = load_json(CHAT_FILE, {})
    sid = str(uuid.uuid4())
    chats[sid] = {"pdf_id": pdf_id, "messages": []}
    save_json(CHAT_FILE, chats)
    return {"session_id": sid}


@app.route("/history", methods=["POST"])
def history():
    sid = request.json.get("session_id")
    chats = load_json(CHAT_FILE, {})
    return chats.get(sid, {}).get("messages", [])


@app.route("/process-pdf", methods=["POST"])
def process_pdf():
    raw    = request.json.get("pdf_data")
    pdf_id = request.json.get("pdf_id")

    if not raw or not pdf_id:
        return {"error": "pdf_data & pdf_id required"}, 400

    docs = load_json(DOC_FILE, {"chunks": []})
    docs["chunks"] = [c for c in docs["chunks"] if c["pdf_id"] != pdf_id]

    pdf_bytes = base64.b64decode(raw)
    cid = len(docs["chunks"])

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:

            total_pages = len(pdf.pages)

            for pno, page in enumerate(pdf.pages, 1):
                print(f"Processing page {pno}/{total_pages}")

                text = page.extract_text() or ""

                if not text.strip():
                    continue

                # tables → structured text
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        text += "\n" + " | ".join([str(c) if c else "" for c in row])

                # OCR fallback (only if tesseract is installed)
                if TESSERACT_AVAILABLE and len(text.strip()) < 40:
                    img = page.to_image(resolution=300).original
                    text = pytesseract.image_to_string(img)

                for c in chunk_text(text):

                    if len(c.split()) < 30:
                        continue

                    emb = hf_embed(c)
                    if not emb:
                        continue

                    docs["chunks"].append({
                        "id":        cid,
                        "pdf_id":    pdf_id,
                        "page":      pno,
                        "text":      c,
                        "embedding": emb
                    })
                    cid += 1

                    if cid > MAX_CHUNKS_PER_PDF:
                        break

    except Exception as e:
        print("PDF error:", e)
        return {"error": "failed to read pdf"}, 500

    save_json(DOC_FILE, docs)

    global DOC_CACHE
    DOC_CACHE = docs

    total_chunks = len([c for c in docs["chunks"] if c["pdf_id"] == pdf_id])

    if total_chunks == 0:
        return {
            "error": "PDF received but no content could be embedded. "
                     "Check that HF_API_KEY is set or HuggingFace API is reachable."
        }, 500

    return {"success": True, "chunks": total_chunks}


@app.route("/query", methods=["POST"])
def query():
    global DOC_CACHE

    q   = request.json.get("question")
    sid = request.json.get("session_id")

    chats   = load_json(CHAT_FILE, {})
    session = chats.get(sid)
    if not session:
        return {"answer": "Invalid session."}

    if DOC_CACHE is None:
        load_doc_cache()

    pdf_id = session["pdf_id"]
    qemb   = hf_embed(q)

    docs = [d for d in DOC_CACHE["chunks"] if d["pdf_id"] == pdf_id]
    if not docs:
        return {"answer": "PDF not processed yet."}

    scored = sorted(
        [(cosine(qemb, d["embedding"]), d) for d in docs],
        key=lambda x: x[0],
        reverse=True
    )

    if scored[0][0] < 0.28:
        ans = "Answer is not present in the PDF."
    else:
        ctx = "\n\n".join(d["text"] for _, d in scored[:8])

        prompt = f"""You are ChatPDF AI.

Use ONLY the provided context.

Rules:
1. If answer is in context → answer normally.
2. If partly present → explain using context only.
3. If not present → say exactly:
   "Answer is not present in the PDF."
4. Do NOT use outside knowledge.
5. Keep answers short.

Context:
{ctx}

Question:
{q}

Answer:
"""
        ans = generate(prompt)

    session["messages"].append({"role": "user", "text": q})
    session["messages"].append({"role": "ai",   "text": ans})
    save_json(CHAT_FILE, chats)

    return {"answer": ans}


if __name__ == "__main__":
    load_doc_cache()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
