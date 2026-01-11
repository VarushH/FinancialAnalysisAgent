# app/agents/compliance.py
from app.compliance.rules import check_rules
from app.compliance.scorer import score_compliance

def compliance_agent(state):
    findings = check_rules(state["extracted_data"])
    score = score_compliance(findings)

    state["compliance"] = {
        "findings": findings,
        "score": score
    }
    return state
