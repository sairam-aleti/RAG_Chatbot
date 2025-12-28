import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_and_chunk_pdf(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    Load PDF and split into chunks, preserving page metadata as `source_page`.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File '{file_path}' not found.")

    loader = PyPDFLoader(file_path)
    raw_documents = loader.load()

    for doc in raw_documents:
        page_num = doc.metadata.get("page", 0) + 1
        doc.metadata["source_page"] = page_num

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(raw_documents)

    for c in chunks:
        c.metadata.setdefault("source_page", 1)

    return chunks, raw_documents