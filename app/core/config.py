import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    mongo_uri: str | None

    pdf_path: str = "data/data.pdf"
    vector_store_path: str = "vector_store_faiss"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    bm25_k: int = 4
    vector_k: int = 4
    rrf_k: int = 60
    fused_top_k: int = 6

    groq_model_name: str = "llama-3.3-70b-versatile"
    temperature: float = 0.0

def get_settings() -> Settings:
    groq = os.getenv("GROQ_API_KEY")
    if not groq:
        raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

    return Settings(
        groq_api_key=groq,
        mongo_uri=os.getenv("MONGO_URI"),
    )