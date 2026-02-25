# ChatPDF AI 🤖📄

A local, privacy-first AI chatbot that lets you upload a PDF and ask questions about it — powered by **Ollama** (llama3 + nomic-embed-text) and **Flask**.

---

## Prerequisites

| Tool | Purpose |
|---|---|
| Python 3.10+ | Backend runtime |
| [Ollama](https://ollama.com) | Local LLM & embeddings |
| [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) | OCR fallback for scanned PDFs |

### Pull required Ollama models

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

---

## Setup

### 1. Install backend dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure Tesseract path

In `backend/app.py`, update this line to match your Tesseract install location:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 3. Start the backend

```bash
python app.py
```

Backend runs at: `http://localhost:5000`

### 4. Open the frontend

Open `frontend/index.html` directly in your browser (no server needed).

---

## Usage

1. Click the 📎 paperclip icon to upload a PDF
2. Wait for processing (embedding takes a moment for large PDFs)
3. Type your question and hit ✈️ send
4. Use **＋ New Chat** to start a fresh conversation on the same PDF

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Check server status |
| `/process-pdf` | POST | Upload and embed a PDF |
| `/new-chat` | POST | Create a new chat session |
| `/history` | POST | Load previous chat messages |
| `/query` | POST | Ask a question about the PDF |

---

## Project Structure

```
chatpdf-ai/
├── backend/
│   ├── app.py             # Flask API + RAG logic
│   ├── requirements.txt   # Python dependencies
│   └── storage/           # Auto-created JSON storage
└── frontend/
    ├── index.html         # Main UI
    ├── app.js             # Frontend logic
    ├── style.css          # Styling
    └── logo.png           # Branding
```
