# app/agents/extractor.py
from app.documents.pdf_extractor import extract_tables
from app.documents.financial_parser import parse_financials

def extract_agent(state):
    pdf_path = state["pdf_path"]
    tables = extract_tables(pdf_path)
    parsed = parse_financials(tables)

    state["extracted_data"] = parsed
    return state
