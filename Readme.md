# Verifiable Hybrid RAG Chatbot (FastAPI + Groq + FAISS + MongoDB)

Production-ready Retrieval-Augmented Generation chatbot that answers questions from uploaded PDFs using **Hybrid Search (BM25 + Vector + RRF fusion)**. The app serves a web UI, returns **citation-backed answers**, persists **chat history in MongoDB**, and ships with **JWT-based signup/login**.

---

## Features

- Upload and index PDFs (up to 50MB) with chunking + FAISS embeddings
- Hybrid retrieval: BM25 keyword + FAISS vector search with Reciprocal Rank Fusion
- Groq LLM for grounded generation
- Source citations with page + preview
- Persistent chat history in MongoDB
- JWT auth (signup/login) protecting API routes
- Web UI served by FastAPI at `/`

---

## Project Structure

```
rag_chatbot_api/
├─ app/
│  ├─ main.py               # FastAPI entrypoint
│  ├─ api/                  # Auth, chat, upload routes
│  ├─ rag/                  # Retrieval + LLM pipeline
│  ├─ memory/               # Conversation history
│  ├─ schemas/              # Pydantic models
│  └─ core/                 # Config and settings
├─ templates/
│  └─ index.html            # Web UI
├─ static/
│  └─ app.js                # Frontend logic
├─ uploaded_pdfs/           # Created on first upload
├─ vector_store_faiss/      # Created on first index
├─ requirements.txt
└─ .env                     # Create locally (do NOT commit)
```

---

## Prerequisites

- Python 3.10+
- Groq API key
- MongoDB connection string (Atlas recommended)

---

## Setup (Conda recommended)

1) Create and activate environment

```bash
conda create -n rag_friend python=3.10 -y
conda activate rag_friend
```

2) Install dependencies

```bash
python -m pip install -r requirements.txt
```

3) Create `.env` in the project root (same level as `app/`, `templates/`, `static/`)

```
GROQ_API_KEY=your_groq_key_here
MONGO_URI=your_mongo_uri_here
JWT_SECRET=your_jwt_secret_here
JWT_EXPIRE_MIN=43200
```

Generate a strong `JWT_SECRET` locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Run Locally

Development (auto-reload):

```bash
uvicorn app.main:app --reload
```

Open the UI at: http://127.0.0.1:8000/

Production-like (no reload):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## How to Use

1. Open the web app in your browser.
2. Sign up and log in.
3. Upload a PDF (index builds automatically).
4. Ask questions in chat.
5. Expand the Sources panel to verify citations.

---

## Common Issues

1) `email-validator` missing

```bash
pip install email-validator
```

2) `bcrypt`/`passlib` issues on Windows

```bash
pip install bcrypt==4.0.1
```

3) MongoDB connection errors
- Ensure `MONGO_URI` is valid and IP access is allowed in Atlas.
- If Mongo is down, signup/login will fail.

4) First run is slow
- `sentence-transformers` downloads model files on first use.

---

## Security Notes

- Never commit `.env` to source control.
- Keep `JWT_SECRET` private; tokens protect API access.
- Passwords are hashed with bcrypt (72-character limit enforced).

---

## License

For portfolio/demo use. Add a license if you plan to open-source.
