import os
from langchain_community.vectorstores import FAISS

def save_vector_store(vector_store, path: str):
    vector_store.save_local(path)

def load_vector_store(embedding_model, path: str):
    return FAISS.load_local(path, embedding_model, allow_dangerous_deserialization=True)

def create_or_load_vector_store(chunks, embedding_model, path: str):
    if os.path.exists(path):
        return load_vector_store(embedding_model, path)

    vector_store = FAISS.from_documents(chunks, embedding_model)
    save_vector_store(vector_store, path)
    return vector_store