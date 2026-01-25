# backend/agents/finance_analysis.py
"""
Finance analysis agent.
Analyzes document content for financial insights.
"""

import asyncio
from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


@agent_retry(agent_name="finance_analysis")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for finance analysis.
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
    
    await asyncio.sleep(0.1)  # Simulate processing
    
    # Analysis logic
    text = " ".join(pages).lower()
    has_revenue = "revenue" in text or "income" in text
    has_expenses = "expense" in text or "cost" in text
    has_profit = "profit" in text or "earnings" in text
    
    print(f"      → Revenue/income detected: {has_revenue}")
    print(f"      → Expenses/cost detected: {has_expenses}")
    print(f"      → Profit/earnings detected: {has_profit}")
    
    analysis_parts = [
        f"The document contains {len(pages)} pages and {len(tables)} tables."
    ]
    
    if has_revenue:
        analysis_parts.append("Revenue/income information detected.")
    if has_expenses:
        analysis_parts.append("Expense/cost data detected.")
    if has_profit:
        analysis_parts.append("Profit/earnings metrics detected.")
    
    if not (has_revenue or has_expenses or has_profit):
        analysis_parts.append("General financial content analyzed.")
    
    analysis = " ".join(analysis_parts)
    state["analysis_result"] = analysis
    
    print(f"   ✅ Analysis: {analysis[:60]}...")
    state = add_message(state, "finance_analysis", "Finance analysis completed")
    return state


# Legacy sync process function
def process(pages, tables, send_message):
    """Legacy synchronous process function."""
    send_message("Finance analysis started")
    page_count = len(pages)
    table_count = len(tables)
    analysis = (
        f"The document contains {page_count} pages and {table_count} tables. "
        f"It discusses financial data and trends. (Dummy analysis)"
    )
    send_message("Finance analysis completed")
    return analysis
