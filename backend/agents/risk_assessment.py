#A mock risk assessment agent. It uses simple heuristics on the text or compliance flags to assign a risk level.

# backend/agents/risk_assessment.py
def process(pages, compliance_result, send_message):
    send_message("Risk assessment started")
    if "fraud" in compliance_result:
        risk = "High"
    elif "loss" in " ".join(pages).lower():
        risk = "Medium"
    else:
        risk = "Low"
    result = f"Overall risk assessment: {risk} risk."
    send_message("Risk assessment completed")
    return result
