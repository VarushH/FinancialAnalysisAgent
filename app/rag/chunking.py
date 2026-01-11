from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_document(
    text: str,
    metadata: Dict,
    chunk_size: int = 800,
    chunk_overlap: int = 150
) -> List[Dict]:
    """
    Parent–child chunking with metadata inheritance.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    chunks = splitter.split_text(text)
    chunked_docs = []

    for idx, chunk in enumerate(chunks):
        chunked_docs.append({
            "content": chunk,
            "metadata": {
                **metadata,
                "chunk_id": idx,
                "parent_doc": metadata.get("doc_id")
            }
        })

    return chunked_docs
