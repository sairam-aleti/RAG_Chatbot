from __future__ import annotations

import os
import shutil
from typing import Callable

from fastapi import APIRouter, File, HTTPException, UploadFile, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

router = APIRouter(tags=["upload"])

# ---- Auth dependency ----
_bearer = HTTPBearer(auto_error=False)
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"

def get_current_user_id(request: Request) -> str:
    creds: HTTPAuthorizationCredentials | None = request.state._auth_creds if hasattr(request.state, "_auth_creds") else None
    # The above line won't be set automatically; so we decode from header here:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization token")
    token = auth.split(" ", 1)[1].strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token (no sub)")
        return str(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _safe_filename(name: str) -> str:
    name = name.replace("\\", "_").replace("/", "_").strip()
    if not name.lower().endswith(".pdf"):
        name = name + ".pdf"
    return name


@router.post("/upload_pdf")
def upload_pdf(request: Request, file: UploadFile = File(...)):
    """
    Upload a PDF and rebuild the RAG index.
    Requires Authorization: Bearer <token>
    """
    user_id = get_current_user_id(request)

    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Get rebuild callback from app.state (set in main.py)
    rebuild: Callable[[str], dict] | None = getattr(request.app.state, "rebuild_from_pdf", None)
    if rebuild is None:
        raise HTTPException(status_code=500, detail="Server not ready: rebuild callback not configured")

    os.makedirs("uploaded_pdfs", exist_ok=True)
    filename = f"{user_id}_{_safe_filename(file.filename or 'uploaded.pdf')}"
    save_path = os.path.join("uploaded_pdfs", filename)

    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    try:
        info = rebuild(save_path)
        return {"filename": filename, **info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))