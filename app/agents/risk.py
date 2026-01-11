# app/agents/risk.py
from app.risk.scoring import risk_score

def risk_agent(state):
    risk = risk_score(
        state["financial_analysis"],
        state["compliance"]
    )

    state["risk"] = risk
    return state
