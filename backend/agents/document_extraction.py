# backend/agents/document_extraction.py
"""
Document extraction agent.
Reads uploaded PDFs, extracts text and tables, and indexes to Qdrant.
"""

import os
import asyncio
import fitz  # PyMuPDF
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry

# Initialize embedding model
print("   📦 Loading HuggingFace embedding model...")
EMBED_MODEL = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
print("   ✅ Embedding model loaded")


def extract_text_and_tables(pdf_path: str) -> tuple[list[str], int, list]:
    """
    Extract text pages and tables from a PDF file.
    """
    print(f"      → Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    print(f"      → Extracted {len(pages)} pages of text")
    
    try:
        import camelot
        print("      → Extracting tables with Camelot...")
        tables = camelot.read_pdf(pdf_path, pages='all')
        table_count = len(tables)
        print(f"      → Found {table_count} tables")
    except Exception as e:
        print(f"      → Table extraction skipped: {e}")
        tables = []
        table_count = 0
    
    return pages, table_count, tables


def index_to_qdrant(pages: list[str], session_id: int) -> None:
    """
    Index document pages to Qdrant vector store.
    """
    try:
        print(f"      → Connecting to Qdrant...")
        client = QdrantClient(
            host=os.getenv('QDRANT_HOST', 'localhost'),
            port=int(os.getenv('QDRANT_PORT', 6333)),
            timeout=5
        )
        
        vector_size = len(EMBED_MODEL.embed_query("test"))
        print(f"      → Vector size: {vector_size}")
        
        try:
            client.recreate_collection(
                collection_name='financial_docs',
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            print(f"      → Created/recreated collection 'financial_docs'")
        except Exception:
            pass
        
        points = []
        for idx, text in enumerate(pages):
            vector = EMBED_MODEL.embed_query(text)
            point = {
                "id": session_id * 1000 + idx,
                "vector": vector,
                "payload": {"session": session_id, "content": text[:100]}
            }
            points.append(point)
        
        if points:
            client.upsert(collection_name='financial_docs', points=points)
            print(f"      → Indexed {len(points)} vectors to Qdrant")
    except Exception as e:
        print(f"      ⚠️  Qdrant indexing skipped (not available): {e}")


@agent_retry(agent_name="document_extraction")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for document extraction.
    """
    print("\n   📄 DOCUMENT EXTRACTION AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "document_extraction", "Document extraction started")
    state["current_agent"] = "document_extraction"
    state["status"] = "processing"
    
    file_path = state.get("file_path")
    if not file_path:
        print("   ❌ Error: No file path provided")
        return set_error(state, "document_extraction", "No file path provided")
    
    print(f"      File: {file_path}")
    
    # Run extraction in thread pool
    loop = asyncio.get_event_loop()
    print("      → Running PDF extraction...")
    pages, table_count, tables = await loop.run_in_executor(
        None, extract_text_and_tables, file_path
    )
    
    # Index to Qdrant (optional)
    session_id = state.get("session_id", 0)
    await loop.run_in_executor(None, index_to_qdrant, pages, session_id)
    
    # Update state
    state["pages"] = pages
    state["table_count"] = table_count
    state["tables"] = [t.df.to_dict() if hasattr(t, 'df') else {} for t in tables]
    
    print(f"   ✅ Extraction complete: {len(pages)} pages, {table_count} tables")
    state = add_message(
        state, 
        "document_extraction", 
        f"Document extraction completed ({len(pages)} pages, {table_count} tables)"
    )
    
    return state


# Legacy sync process function
def process(session, send_message):
    """Legacy synchronous process function."""
    send_message("Document extraction started")
    file_path = session.file.path
    pages, table_count, tables = extract_text_and_tables(file_path)
    index_to_qdrant(pages, session.id)
    session.pages = pages
    session.table_count = table_count
    session.send_message = send_message
    send_message(f"Document extraction completed ({len(pages)} pages, {table_count} tables)")
    return pages, tables