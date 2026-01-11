from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.0
)

def rerank(query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
    """
    Cross-encoder style re-ranking using Gemini.
    """
    scored = []

    for doc in documents:
        prompt = f"""
        Query: {query}

        Document:
        {doc}

        Score relevance from 0 to 10.
        Respond with only the number.
        """
        try:
            score = float(llm.invoke(prompt).content.strip())
        except Exception:
            score = 0.0

        doc["score"] = score
        scored.append(doc)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
