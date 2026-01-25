#This agent reads the uploaded PDF, extracts text (using PyMuPDF) and tables (using Camelot), and indexes the text into Qdrant for later retrieval. It sends a progress message when done. This example splits the document into pages and stores embeddings in a financial_docs collection in Qdrant.

# backend/agents/document_extraction.py
import os
import fitz  # PyMuPDF
# import camelot
from langchain_huggingface import HuggingFaceEmbeddings

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# EMBED_MODEL = SentenceTransformer('all-MiniLM-L6-v2')  # lightweight embedding model
EMBED_MODEL = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
def extract_text_and_tables(pdf_path):
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    try:
        tables = camelot.read_pdf(pdf_path, pages='all')
        table_count = len(tables)
    except Exception:
        tables = []
        table_count = 0
    return pages, table_count, tables

def index_to_qdrant(pages, session_id):
    # Connect to Qdrant
    client = QdrantClient(host=os.getenv('QDRANT_HOST', 'qdrant'), port=int(os.getenv('QDRANT_PORT', 6333)))
    # Create collection if not exists
    vector_size = len(EMBED_MODEL.embed_query("test"))
    try:
        client.recreate_collection(
            collection_name='financial_docs',
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
    except Exception:
        # If collection exists or recreate fails, ignore
        pass

    points = []
    for idx, text in enumerate(pages):
        vector = EMBED_MODEL.embed_query(text)
        point = {
            "id": session_id * 1000 + idx,  # unique ID per session page
            "vector": vector,
            "payload": {"session": session_id, "content": text[:100]}  # store snippet
        }
        points.append(point)
    if points:
        client.upsert(collection_name='financial_docs', points=points)

def process(session, send_message):
    send_message("Document extraction started")
    file_path = session.file.path
    pages, table_count, tables = extract_text_and_tables(file_path)
    # Store data in Qdrant
    index_to_qdrant(pages, session.id)
    # Attach results to session (in-memory)
    session.pages = pages
    session.table_count = table_count
    session.send_message = send_message
    send_message(f"Document extraction completed ({len(pages)} pages, {table_count} tables)")
    # Store extracted data for next agents
    return pages, tables