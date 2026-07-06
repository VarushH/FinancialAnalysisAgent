# backend/agents/finance_analysis.py
"""
Finance analysis agent.
Analyzes document content for financial insights.
"""

import asyncio
import re
import math
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.documents import Document

# RAG Imports
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_core.stores import InMemoryStore
from qdrant_client import QdrantClient
from sentence_transformers import CrossEncoder
from django.conf import settings

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


# --- Cross-Encoder Re-ranker (lazy singleton) ---
_reranker = None

def _get_reranker():
    """Load the cross-encoder once, on first use (keeps Django startup fast)."""
    global _reranker
    if _reranker is None:
        print("   📦 Loading cross-encoder re-ranker...")
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        print("   ✅ Re-ranker loaded")
    return _reranker


def rerank_documents(query: str, documents: list, top_n: int = 4) -> list:
    """
    Re-score retrieved documents against the query with a cross-encoder and return
    the top_n most relevant.

    Bi-encoder retrieval (the embedding search) scores query and passage separately,
    so it's fast over the whole corpus but coarse. A cross-encoder reads (query, passage)
    TOGETHER, so it judges relevance far more accurately — but is too slow to run on the
    corpus. Running it only on the retrieved shortlist is the standard two-stage pattern:
    retrieve wide and cheap, then re-rank narrow and precise.
    """
    if not documents:
        return []
    reranker = _get_reranker()
    pairs = [(query, doc.page_content) for doc in documents]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(documents, scores), key=lambda pair: pair[1], reverse=True)
    return [doc for doc, _ in ranked[:top_n]]


def _parse_financial_value(raw) -> float:
    """
    Parse a free-text financial string ('USD 120.0 million', '1,050M', '15') into a
    float normalized to millions. Returns NaN if unparseable, so YoY/margin math
    downstream degrades gracefully instead of crashing or fabricating a number.
    """
    if raw is None:
        return float('nan')
    s = str(raw).lower().replace(',', '').strip()
    if not s or s in ('n/a', 'na', 'none', '-'):
        return float('nan')
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    if not m:
        return float('nan')
    val = float(m.group())
    # Normalize magnitude to a common "millions" base so ratios stay consistent.
    if 'trillion' in s:
        val *= 1_000_000
    elif 'billion' in s or re.search(r'\d\s*b\b', s):
        val *= 1_000
    elif 'thousand' in s or re.search(r'\d\s*k\b', s):
        val *= 0.001
    # 'million'/'m' or bare number => base unit (x1)
    return val



# NEW: Pydantic models for extraction
class SignificantDate(BaseModel):
    date: str = Field(description="The date or fiscal period (e.g., FY2024, 2023)")
    significance: str = Field(description="Why this date is important (e.g., Revenue peak, report end date)")

class PeriodFinancials(BaseModel):
    period: str = Field(description="Fiscal period label exactly as written in the document, e.g. 'FY2024', '2023', 'Year ended Dec 2022'")
    revenue: str = Field(description="Total revenue for this period")
    net_income: str = Field(description="Net income for this period")
    total_assets: str = Field(description="Total assets for this period")
    total_liabilities: str = Field(description="Total liabilities for this period")
    total_equity: str = Field(description="Total shareholder's equity for this period")
    debt_to_equity: str = Field(description="Debt-to-equity ratio for this period")

class FinancialSummary(BaseModel):
    periods: List[PeriodFinancials] = Field(description="One entry per fiscal period present in the document, ordered most-recent first")
class ExtractionResult(BaseModel):
    companies: List[str] = Field(description="List of all company names mentioned")
    currencies: List[str] = Field(description="List of currency values (e.g., USD 120M)")
    numbers: List[str] = Field(description="Significant non-currency numbers or ratios")
    important_dates: List[SignificantDate] = Field(description="List of dates and their context")
    financial_summary: FinancialSummary

# Setup LLM and Parser
parser = PydanticOutputParser(pydantic_object=ExtractionResult)
# Note: In a real production environment, API keys should be in settings/env vars.
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.2,
    timeout=None,
    max_retries=2
)

# --- RAG Helper Functions ---

def setup_rag_pipeline(pages: List[str], collection_name: str = "financeagent"):
    """
    Sets up the RAG pipeline with Qdrant vector store.
    
    Indexes the provided document pages into a Qdrant collection using HuggingFace embeddings.
    Returns a retriever object that can be used to query the document content.

    Args:
        pages (List[str]): List of text content from document pages.
        collection_name (str): The name of the Qdrant collection to use/create.

    Returns:
        VectorStoreRetriever: A LangChain retriever initialized with the document index.
    """

    print(f"      Initializing RAG pipeline for collection: {collection_name}")
    
    # 1. Setup splitters
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
    
    # 2. Setup Embeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # 3. Setup Qdrant Client
    

    qdrant_client = QdrantClient(
        url=settings.QDRANT_URL, 
        api_key=settings.QDRANT_API_KEY,
    )
    
    # Check/Create Collection
    if not qdrant_client.collection_exists(collection_name=collection_name):
        print(f"      Collection '{collection_name}' does not exist, creating...")
        qdrant_client.create_collection(
            collection_name, 
            vectors_config={
                "size": 384,
                "distance": "Cosine"
            }
        )
    else:
        print(f"      Collection '{collection_name}' already exists.")

    # 4. Setup VectorStore
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    
    # 5. Setup DocStore and Retriever
    doc_store = InMemoryStore()
    parent_document_retriever = ParentDocumentRetriever(
        vectorstore=vector_store,
        docstore=doc_store,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
    )
    
    # 6. Prepare and Add Documents
    docs = [Document(page_content=page, metadata={"author": "Varush0", "page": i}) for i, page in enumerate(pages)]
    
    print(f"      Indexing {len(docs)} documents into ParentDocumentRetriever...")
    parent_document_retriever.add_documents(docs)
    
    # Configure search kwargs
    # Note: Qdrant filter format can be strict. Disabling strict filter for this demo to ensure basic retrieval works.
    # If filtering is needed, it must match Qdrant's Filter model constraints (using 'must', 'match', etc.)
    # parent_document_retriever.search_kwargs = {
    #     "k": 1,
    #     "filter": {"author": 'Varush0'}
    # }
    parent_document_retriever.search_kwargs = {"k": 15}
    
    return parent_document_retriever

def expand_query(query: str):
    """
    Expands the search query using ChatGroq.
    """
    query_expansion_prompt = PromptTemplate(
        input_variables=["query"],
        template="""You are a search query expansion expert. Your task is to expand and improve the given query
        to make it more detailed and comprehensive. Include relevant synonyms and related terms to improve retrieval.
        Return only the expanded query without any explanations or additional text.

        Original query: {query}

        Expanded query:"""
    ).format(query=query)

    query_expansion_model = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=settings.GROQ_API_KEY,
        temperature=0.3,
        timeout=None,
        max_retries=2
    )
    
    expanded_query = query_expansion_model.invoke(query_expansion_prompt)
    return expanded_query.content.strip()


def generate_rag_answer(query: str, context: str) -> str:
    """
    Generates a natural language answer based on the query and retrieved context.
    """
    answer_prompt = ChatPromptTemplate.from_template(
        """You are a helpful financial analyst assistant. 
        Answer the user's question strictly based on the provided context.
        If the context does not contain the answer, say "I cannot find the answer in the provided document properties."
        
        Context:
        {context}
        
        Question: 
        {query}
        
        Answer (be concise and direct):"""
    )
    
    chain = answer_prompt | llm
    response = chain.invoke({"context": context, "query": query})
    return response.content.strip()


def extract_with_llm(text_list, tables_list_dicts):
    """
    Extract structured financial data using LLM.
    tables_list_dicts is a list of dicts (converted from dfs previously), needs reconstruction to CSV for context.
    """
    # Combine text
    combined_content = "\n".join(text_list[:10]) # Limit to first 10 pages to avoid token limits if very large
    
    # Process tables (tables are stored as dicts in state)
    for t_dict in tables_list_dicts:
        try:
            df = pd.DataFrame.from_dict(t_dict)
            combined_content += "\n" + df.to_csv(index=False)
        except Exception:
            pass

    prompt = ChatPromptTemplate.from_template(
        "Extract specific financial data from the following document content.\n"
        "{format_instructions}\n"
        "Content:\n{context}"
        """Instructions: 
             1. Currency extracted should not have numbers, it should have the unique currency types available in the document
             2. Number extracted must have significance written along for better interpretation of result
             3. The dates should be extracted only if it has proper format written in Date,Month,Year format along with its significance.
             4. For financial_summary, extract a SEPARATE entry for EVERY fiscal period/year shown in the document (e.g. current and prior years in a comparative statement), ordered most-recent first. Do not merge years. If a metric is absent for a period, use "N/A".
        """
    )

    chain = prompt | llm | parser

    try:
        return chain.invoke({
            "context": combined_content[:50000], # Hard cap context char count
            "format_instructions": parser.get_format_instructions()
        })
    except Exception as e:
        print(f"      Running extraction failed: {e}")
        return None


@agent_retry(agent_name="finance_analysis")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for finance analysis.
    
    Orchestrates the financial analysis workflow:
    1. Indexes document pages into Qdrant for RAG.
    2. Uses RAG to answer specific financial queries.
    3. Extracts structured financial data using LLM.
    4. Updates state with analysis results and RAG findings.

    Args:
        state (AgentState): Current workflow state.

    Returns:
        AgentState: Updated state with 'analysis_result', 'rag_response', and 'financial_extraction'.
    """
    print("\n   💰 FINANCE ANALYSIS AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "finance_analysis", "Finance analysis started")
    state["current_agent"] = "finance_analysis"
    
    pages = state.get("pages", [])
    tables = state.get("tables", [])
    
    print(f"      Analyzing {len(pages)} pages and {len(tables)} tables...")
    
    if not pages:
        print("   ❌ Error: No pages available")
        return set_error(state, "finance_analysis", "No pages available for analysis")
    
    # --- RAG Execution ---
    try:
        print("      → Setting up RAG pipeline (ParentDocumentRetriever)...")
        loop = asyncio.get_event_loop()
        
        # Run synchronous RAG setup in executor to avoid blocking
        # Use session-specific collection to ensure InMemoryStore (docstore) matches Qdrant indices
        session_id = state.get("session_id", "default")
        collection_name = f"session_{session_id}"
        print(f"      → Using Qdrant collection: {collection_name}")
        
        retriever = await loop.run_in_executor(None, setup_rag_pipeline, pages, collection_name)
        
        # Check for user query in state
        user_query = state.get("user_query")
        if user_query:
            target_query = user_query
            print(f"      → Using User Query: '{target_query}'")
        else:
            target_query = "How does the company prepare consolidated financial statements?"
            print(f"      → Using Default Query: '{target_query}'")

        print(f"      → Expanding Query: '{target_query}'")
        
        expanded_query = await loop.run_in_executor(None, expand_query, target_query)
        print(f"      → Expanded Query result: '{expanded_query}'")
        
        print("      → Invoking Retriever...")
        results = await loop.run_in_executor(None, retriever.invoke, expanded_query)
        
        if results:
            print(f"      ✅ Retrieved {len(results)} candidate chunks. Re-ranking...")
            # Re-rank against the ORIGINAL query, not the expanded one: expansion
            # maximizes retrieval recall, but relevance should be judged on true intent.
            reranked = await loop.run_in_executor(
                None, rerank_documents, target_query, results, 4
            )
            print(f"      ✅ Kept top {len(reranked)} chunk(s) after re-ranking.")
            
            # Answer from the combined top chunks, not just the single best.
            context = "\n\n---\n\n".join(doc.page_content for doc in reranked)
            source_pages = sorted({str(doc.metadata.get('page', 'N/A')) for doc in reranked})
            
            print("      → Generating Q&A response...")
            rag_answer = await loop.run_in_executor(None, generate_rag_answer, target_query, context)
            
            rag_response = f"Q: {target_query}\n\nA: {rag_answer}\n\n(Sources: Page(s) {', '.join(source_pages)})"
            state["rag_response"] = rag_response
            
        else:
            print("      ⚠️ RAG Retrieval returned no results.")
            state["rag_response"] = "RAG retrieved no context for the query."
            
    except Exception as e:
        print(f"      ❌ RAG Pipeline failed: {e}")
        state["rag_response"] = f"RAG Pipeline encountered an error: {str(e)}"
        # Don't fail the whole agent for this demo feature, just log it
    
    # Run LLM Extraction (Existing Logic)
    print("      → Running LLM extraction...")
    loop = asyncio.get_event_loop()
    extraction_result = await loop.run_in_executor(None, extract_with_llm, pages, tables)
    
    if extraction_result:
        print("      ✅ LLM Extraction successful")
        # Store as dict for serialization
        state["financial_extraction"] = extraction_result.dict()
        
        # Create a summary string for the legacy analysis field
        fs = extraction_result.financial_summary
        if fs.periods:
            latest = fs.periods[0]
            n_periods = len(fs.periods)
            period_labels = ", ".join(p.period for p in fs.periods)

            rev = _parse_financial_value(latest.revenue)
            ni = _parse_financial_value(latest.net_income)

            # Net margin for the latest period (units cancel in the ratio)
            margin_txt = ""
            if not math.isnan(rev) and rev != 0 and not math.isnan(ni):
                margin_txt = f" (net margin {ni / rev:.1%})"

            # Year-over-year revenue vs the prior period + a one-line trend read
            yoy_txt, trend_txt = "", ""
            if n_periods >= 2:
                prev = fs.periods[1]
                prev_rev = _parse_financial_value(prev.revenue)
                if not math.isnan(rev) and not math.isnan(prev_rev) and prev_rev != 0:
                    yoy = (rev - prev_rev) / abs(prev_rev)
                    direction = "up" if yoy >= 0 else "down"
                    yoy_txt = f" ({'+' if yoy >= 0 else ''}{yoy:.1%} vs {prev.period})"
                    trend_txt = f"Trend: Revenue {direction} {abs(yoy):.1%} YoY ({prev.period}\u2192{latest.period}). "

            analysis_summary = (
                f"Financial Summary \u2014 {n_periods} period(s) analyzed ({period_labels}).\n"
                f"{latest.period}: Revenue {latest.revenue}{yoy_txt}, "
                f"Net Income {latest.net_income}{margin_txt}, Assets {latest.total_assets}.\n"
                f"{trend_txt}"
                f"Extracted: {n_periods} fiscal period(s), "
                f"{len(extraction_result.important_dates)} significant date(s), "
                f"{len(extraction_result.numbers)} key figure(s)."
            )
        else:
            analysis_summary = "Financial summary could not be extracted."
        state["analysis_result"] = analysis_summary
    else:
        print("      ⚠️ LLM Extraction returned no result, falling back to basic analysis")
        state["analysis_result"] = "Basic analysis: Document contains financial data but automated extraction failed."
    
    # Append RAG response if available
    if state.get("rag_response"):
        state["analysis_result"] += f"\n\n[RAG Q&A]\n{state['rag_response']}"
    
    print(f"   ✅ Analysis complete.")
    state = add_message(state, "finance_analysis", "Finance analysis completed")
    return state

# Legacy sync process function
def process(pages, tables, send_message):
    """Legacy synchronous process function."""
    send_message("Finance analysis started")
    # For legacy sync calls, we just return a dummy string to avoid breaking old callers
    analysis = "Legacy process called. Please use async process for full extraction."
    send_message("Finance analysis completed")
    return analysis