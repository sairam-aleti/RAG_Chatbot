from typing import Callable, List
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

def reciprocal_rank_fusion(
    bm25_docs: List[Document],
    vector_docs: List[Document],
    *,
    k: int = 60,
    top_k: int = 6,
) -> List[Document]:
    """
    Fuse BM25 + Vector results with Reciprocal Rank Fusion.
    Score(doc) = sum(1 / (k + rank)) over retrievers.
    """
    rrf_scores: dict[str, float] = {}

    def doc_key(doc: Document) -> str:
        # Same approach as your notebook. Works for demo, but may collide.
        return doc.page_content[:50]

    for rank, doc in enumerate(bm25_docs, 1):
        key = doc_key(doc)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1 / (k + rank))

    for rank, doc in enumerate(vector_docs, 1):
        key = doc_key(doc)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1 / (k + rank))

    all_docs = {doc_key(d): d for d in (bm25_docs + vector_docs)}

    sorted_docs = sorted(
        all_docs.values(),
        key=lambda d: rrf_scores.get(doc_key(d), 0.0),
        reverse=True,
    )
    return sorted_docs[:top_k]

class HybridRetriever(BaseRetriever):
    """
    Custom retriever: BM25 + Vector, then fuse with RRF.
    """
    bm25_retriever: BaseRetriever | None = None
    vector_retriever: BaseRetriever
    rrf_func: Callable[..., List[Document]]

    def _get_relevant_documents(self, query: str) -> List[Document]:
        bm25_results = self.bm25_retriever.invoke(query) if self.bm25_retriever else []
        vector_results = self.vector_retriever.invoke(query)
        return self.rrf_func(bm25_results, vector_results)

def build_hybrid_retriever(
    chunks,
    vector_store,
    *,
    bm25_k: int,
    vector_k: int,
    rrf_k: int,
    fused_top_k: int,
):
    try:
        bm25 = BM25Retriever.from_documents(chunks)
        bm25.k = bm25_k
    except Exception:
        bm25 = None

    vector = vector_store.as_retriever(search_kwargs={"k": vector_k})

    def rrf(bm25_docs, vector_docs):
        return reciprocal_rank_fusion(bm25_docs, vector_docs, k=rrf_k, top_k=fused_top_k)

    return HybridRetriever(bm25_retriever=bm25, vector_retriever=vector, rrf_func=rrf)