import os
import shutil
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.rag.pdf_loader import load_and_chunk_pdf
from app.rag.embeddings import get_embedding_model
from app.rag.vectorstore_faiss import create_or_load_vector_store
from app.rag.hybrid_retriever import build_hybrid_retriever
from app.memory.history import build_history_getter
from app.rag.chain import build_conversational_rag_chain

from app.api.routes_chat import router as chat_router
from app.api.routes_auth import router as auth_router
from app.api.routes_pages import router as pages_router
from app.api.routes_upload import router as upload_router

app = FastAPI(title="RAG Chatbot API", version="1.0")

# Serve /static/* files (app.js, css, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the HTML page at "/"
app.include_router(pages_router)

settings = get_settings()

# MongoDB (if available) for persistent history
get_session_history = build_history_getter(settings.mongo_uri)

# Lazy init: do NOT load/chunk default PDF or build FAISS at startup.
_embedding_model = None


def _ensure_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = get_embedding_model(settings.embedding_model_name)
    return _embedding_model


def _rebuild_from_pdf(pdf_path: str) -> dict:
    """
    Build chunks, vector store, retriever, and chain using the uploaded PDF.
    Updates app.state so routes immediately use the new index.
    """
    emb = _ensure_embedding_model()

    chunks, raw_docs = load_and_chunk_pdf(pdf_path)

    # Fresh rebuild vector store (avoid reloading old index)
    if os.path.exists(settings.vector_store_path):
        shutil.rmtree(settings.vector_store_path, ignore_errors=True)

    vector_store = create_or_load_vector_store(chunks, emb, settings.vector_store_path)

    hybrid_retriever = build_hybrid_retriever(
        chunks,
        vector_store,
        bm25_k=settings.bm25_k,
        vector_k=settings.vector_k,
        rrf_k=settings.rrf_k,
        fused_top_k=settings.fused_top_k,
    )

    conversational_rag_chain = build_conversational_rag_chain(
        groq_api_key=settings.groq_api_key,
        model_name=settings.groq_model_name,
        temperature=settings.temperature,
        hybrid_retriever=hybrid_retriever,
        get_session_history=get_session_history,
    )

    # Update shared state used by routes
    app.state.rag_chain = conversational_rag_chain
    app.state.rag_retriever = hybrid_retriever
    app.state.rag_stats = {
        "pdf_pages": len(raw_docs),
        "chunks": len(chunks),
        "faiss_vectors": int(vector_store.index.ntotal),
        "last_pdf_path": pdf_path,
    }

    return {
        "pages": len(raw_docs),
        "chunks": len(chunks),
        "vectors": int(vector_store.index.ntotal),
    }


@app.on_event("startup")
def _startup():
    # Upload route uses this
    app.state.rebuild_from_pdf = _rebuild_from_pdf

    # Chat routes use these (start empty until a PDF is uploaded)
    app.state.rag_chain = None
    app.state.rag_retriever = None
    app.state.rag_stats = {
        "pdf_pages": 0,
        "chunks": 0,
        "faiss_vectors": 0,
        "last_pdf_path": None,
    }


# API routers
app.include_router(auth_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health():
    stats: dict[str, Any] = getattr(app.state, "rag_stats", {}) or {}
    return {
        "status": "ok",
        "rag_ready": bool(getattr(app.state, "rag_chain", None)) and bool(getattr(app.state, "rag_retriever", None)),
        "pdf_pages": int(stats.get("pdf_pages", 0) or 0),
        "chunks": int(stats.get("chunks", 0) or 0),
        "faiss_vectors": int(stats.get("faiss_vectors", 0) or 0),
        "mongo_configured": settings.mongo_uri is not None,
    }