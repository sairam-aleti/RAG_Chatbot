from __future__ import annotations

import json
import os
from typing import Iterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt

from app.schemas.chat import ChatRequest, ChatResponse, Source

router = APIRouter()

# ---- Auth (JWT Bearer) ----
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"


def _get_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization token")
    return auth.split(" ", 1)[1].strip()


def get_current_user_id(request: Request) -> str:
    token = _get_bearer_token(request)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token (no sub)")
        return str(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _scoped_session_id(user_id: str, conversation_id: str) -> str:
    return f"{user_id}:{conversation_id}"


def _get_chain_from_state(request: Request):
    chain = getattr(request.app.state, "rag_chain", None)
    if chain is None:
        raise HTTPException(status_code=500, detail="Server not ready: chain not configured")
    return chain


def _get_retriever_from_state(request: Request):
    retriever = getattr(request.app.state, "rag_retriever", None)
    if retriever is None:
        raise HTTPException(status_code=500, detail="Server not ready: retriever not configured")
    return retriever


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    """
    Non-streaming chat endpoint used by the UI.
    Requires Authorization: Bearer <token>
    """
    user_id = get_current_user_id(request)
    chain = _get_chain_from_state(request)
    retriever = _get_retriever_from_state(request)

    try:
        session_id = _scoped_session_id(user_id, req.conversation_id)
        config = {"configurable": {"session_id": session_id}}

        answer = chain.invoke({"input": req.message}, config=config)

        docs = retriever.invoke(req.message)
        sources: list[Source] = []
        for d in docs:
            page = d.metadata.get("source_page", None)
            preview = d.page_content[:160].replace("\n", " ")
            sources.append(Source(page=page if isinstance(page, int) else None, preview=preview))

        return ChatResponse(answer=answer, sources=sources)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/stream")
def chat_stream(
    request: Request,
    conversation_id: str = Query(...),
    message: str = Query(..., min_length=1),
    hybrid: int = Query(1),  # accepted for UI compatibility; not used yet
):
    """
    Streaming endpoint. Uses fetch streaming in the UI.
    Requires Authorization: Bearer <token>
    """
    user_id = get_current_user_id(request)
    chain = _get_chain_from_state(request)
    retriever = _get_retriever_from_state(request)

    def event_generator() -> Iterator[str]:
        try:
            session_id = _scoped_session_id(user_id, conversation_id)
            config = {"configurable": {"session_id": session_id}}

            streamed_any = False
            try:
                for chunk in chain.stream({"input": message}, config=config):
                    streamed_any = True
                    yield f"event: token\ndata: {json.dumps({'t': str(chunk)})}\n\n"
            except Exception:
                streamed_any = False

            if not streamed_any:
                answer = chain.invoke({"input": message}, config=config)
                yield f"event: token\ndata: {json.dumps({'t': str(answer)})}\n\n"

            docs = retriever.invoke(message)
            sources = []
            for d in docs:
                page = d.metadata.get("source_page", None)
                preview = d.page_content[:160].replace("\n", " ")
                sources.append({"page": page if isinstance(page, int) else None, "preview": preview})

            yield f"event: sources\ndata: {json.dumps({'sources': sources})}\n\n"
            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")