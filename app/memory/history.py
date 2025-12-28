from __future__ import annotations
from typing import Any
from pymongo import MongoClient
from langchain_mongodb.chat_message_histories import MongoDBChatMessageHistory

_in_memory_history: dict[str, list[Any]] = {}

class SimpleMemoryHistory:
    """
    Minimal in-memory fallback that supports what RunnableWithMessageHistory expects.
    Data is lost on restart.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        _in_memory_history.setdefault(session_id, [])
        self.messages = _in_memory_history[session_id]

    def add_message(self, message: Any):
        self.messages.append(message)

    def get_messages(self):
        return self.messages

def build_history_getter(
    mongo_uri: str | None,
    db_name: str = "RAG_Chatbot",
    collection: str = "chat_history",
):
    mongodb_available = False

    if mongo_uri:
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            mongodb_available = True
        except Exception:
            mongodb_available = False

    if mongodb_available:
        def get_session_history(session_id: str):
            return MongoDBChatMessageHistory(
                connection_string=mongo_uri,
                session_id=session_id,
                database_name=db_name,
                collection_name=collection,
            )
        return get_session_history

    def get_session_history(session_id: str):
        return SimpleMemoryHistory(session_id)

    return get_session_history