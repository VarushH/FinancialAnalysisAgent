# app/agents/analyzer.py
from app.risk.ratios import calculate_ratios

def analyzer_agent(state):
    data = state["extracted_data"]
    ratios = calculate_ratios(data)

    state["financial_analysis"] = ratios
    return state
