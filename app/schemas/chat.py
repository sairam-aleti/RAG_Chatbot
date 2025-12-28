from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    conversation_id: str = Field(..., description="Conversation/session id for persistent memory")
    message: str = Field(..., min_length=1)
    hybrid: bool = Field(True, description="If true, use hybrid search; if false, vector-only (UI toggle)")

class Source(BaseModel):
    page: int | None = None
    preview: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]