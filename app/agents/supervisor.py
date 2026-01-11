# app/agents/supervisor.py
def supervisor(state):
    if "extracted_data" not in state:
        return "extract"
    if "financial_analysis" not in state:
        return "analyze"
    if "compliance" not in state:
        return "compliance"
    if "risk" not in state:
        return "risk"
    if "report" not in state:
        return "report"
    return "human_approval"
