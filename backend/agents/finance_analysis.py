#A stub finance analysis agent. For demonstration, it simply summarizes counts. In practice, this could call a machine learning model or LLM. It uses the extracted pages and tables from the previous agent.

# backend/agents/finance_analysis.py
def process(pages, tables, send_message):
    send_message("Finance analysis started")
    # Example analysis: summarize document content and table count
    page_count = len(pages)
    table_count = len(tables)
    analysis = (
        f"The document contains {page_count} pages and {table_count} tables. "
        f"It discusses financial data and trends. (Dummy analysis)"
    )
    send_message("Finance analysis completed")
    return analysis
