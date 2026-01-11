import pdfplumber
from typing import List

def extract_tables(pdf_path: str) -> List[dict]:
    """
    Extracts tables from financial PDFs.
    """
    tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_table()
            if extracted:
                tables.append({
                    "page": page.page_number,
                    "table": extracted
                })

    return tables
