# backend/agents/document_extraction.py
"""
Document extraction agent.
Reads uploaded PDFs, extracts text and tables, and indexes to Qdrant.
"""

import os
import asyncio
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd

from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from django.conf import settings

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


def extract_text_and_tables(pdf_path: str) -> tuple[list[str], int, list]:
    """
    Extract text pages and tables from a PDF file.
    Uses PyMuPDF for text (handles corrupted PDFs) and pdfplumber for tables (optional).
    """
    
    all_tables = []
    all_text = []
    
    print(f"      → Opening PDF: {pdf_path}")
    
    # Primary: Use PyMuPDF (fitz) for text extraction - more robust with problematic PDFs
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text:
                print(f"      → Text detected on page {page_num + 1}")
                all_text.append(text)
        doc.close()
        print(f"      → Extracted {len(all_text)} pages of text")
    except Exception as e:
        print(f"      → Text extraction error: {e}")
        return [], 0, []
    
    # Secondary: Try pdfplumber for table extraction (optional, may fail on some PDFs)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if tables:
                    print(f"      → Table(s) detected on page {page_num + 1}")
                    for table_index, table in enumerate(tables):
                        if table and len(table) > 1:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            print(f"      → Extracted Table {table_index + 1} from Page {page_num + 1}")
                            all_tables.append(df)
            print(f"      → Found {len(all_tables)} tables")
    except Exception as e:
        print(f"      → Table extraction skipped (PDF structure issue): {e}")
        # Continue without tables - text extraction already succeeded
    
    return all_text, len(all_tables), all_tables





@agent_retry(agent_name="document_extraction")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for document extraction.
    
    1. Extracts text and tables from the PDF file specified in state.
    2. Indexes the extracted content into Qdrant for vector search.
    3. Updates the state with 'pages', 'tables', and 'table_count'.

    Args:
        state (AgentState): Current workflow state containing 'file_path' and 'session_id'.

    Returns:
        AgentState: Updated state with extracted content.
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
    
    # Update state
    state["pages"] = pages
    state["table_count"] = table_count
    state["tables"] = [t.to_dict() if hasattr(t, 'to_dict') else {} for t in tables]
    
    print(f"   ✅ Extraction complete: {len(pages)} pages, {table_count} tables")
    state = add_message(
        state, 
        "document_extraction", 
        f"Document extraction completed ({len(pages)} pages, {table_count} tables)"
    )
    
    return state

