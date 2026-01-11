from qdrant_client import QdrantClient
from typing import List, Dict
from app.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)

def search(query: str, limit: int = 10, filters: Dict = None) -> List[Dict]:
    """
    Semantic vector search with optional metadata filters.
    """
    return client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=embed(query),
        limit=limit,
        query_filter=filters
    )


def keyword_search(query: str, limit: int = 10) -> List[Dict]:
    """
    Keyword / sparse search simulation (BM25-style).
    """
    return client.search(
        collection_name=QDRANT_COLLECTION,
        query_text=query,
        limit=limit
    )


def embed(text: str) -> List[float]:
    """
    Embedding function placeholder.
    Replace with Gemini / Vertex embedding.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001"
    )
    return embeddings.embed_query(text)
