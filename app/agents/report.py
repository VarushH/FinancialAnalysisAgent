# app/agents/report.py
from app.llm.gemini import get_gemini

def report_agent(state):
    llm = get_gemini()
    prompt = f"""
    Generate an investment-grade financial report:
    Financials: {state['financial_analysis']}
    Compliance: {state['compliance']}
    Risk: {state['risk']}
    """

    state["report"] = llm.invoke(prompt).content
    return state
