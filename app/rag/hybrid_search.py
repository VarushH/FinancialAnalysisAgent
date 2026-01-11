# app/rag/hybrid_search.py
from app.rag.qdrant_client import qdrant
from app.rag.reranker import rerank

def hybrid_search(query, filters=None):
    semantic = qdrant.search(query, limit=20, filters=filters)
    keyword = qdrant.keyword_search(query, limit=20)
    combined = semantic + keyword
    return rerank(query, combined)
