from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient

from passlib.context import CryptContext
from jose import jwt

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- Config ----
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "43200"))  # 30 days

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "RAG_Chatbot"
USERS_COLLECTION = "users"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Reuse one Mongo client
_mongo_client: MongoClient | None = None


# ---- Schemas ----
class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    # bcrypt only uses first 72 bytes; enforce max_length to avoid runtime crash
    password: str = Field(..., min_length=6, max_length=72)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)

class PublicUser(BaseModel):
    id: str
    name: str
    email: EmailStr
    avatar: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PublicUser


def _get_users_collection():
    global _mongo_client
    if not MONGO_URI:
        raise HTTPException(status_code=500, detail="MONGO_URI not configured in .env")

    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)

    return _mongo_client[DB_NAME][USERS_COLLECTION]


def _user_to_public(doc: dict[str, Any]) -> PublicUser:
    name = doc.get("name", "User")
    return PublicUser(
        id=str(doc["_id"]),
        name=name,
        email=doc["email"],
        avatar=(name[:1].upper() if name else "U"),
    )


def _create_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE_MIN)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


@router.post("/signup", response_model=PublicUser)
def signup(req: SignupRequest):
    users = _get_users_collection()

    email = req.email.lower().strip()
    existing = users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Extra safety (in case someone bypasses Pydantic validation somehow)
    if len(req.password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")

    hashed = pwd_context.hash(req.password)
    doc = {
        "name": req.name.strip(),
        "email": email,
        "password_hash": hashed,
        "created_at": datetime.now(timezone.utc),
    }
    result = users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _user_to_public(doc)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    users = _get_users_collection()

    email = req.email.lower().strip()
    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if len(req.password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")

    if not pwd_context.verify(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(str(user["_id"]), user["email"])
    return LoginResponse(access_token=token, user=_user_to_public(user))