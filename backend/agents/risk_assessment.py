# backend/agents/risk_assessment.py
"""
Risk assessment agent.
Evaluates document content and compliance findings to determine risk level.
"""

import asyncio
from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry

RISK_KEYWORDS = {
    'high': ['fraud', 'illegal', 'sanction', 'default', 'bankruptcy', 'lawsuit'],
    'medium': ['loss', 'decline', 'risk', 'debt', 'liability', 'concern'],
    'low': ['stable', 'growth', 'profit', 'compliance', 'audit']
}


@agent_retry(agent_name="risk_assessment")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for risk assessment.
    """
    print("\n   📊 RISK ASSESSMENT AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "risk_assessment", "Risk assessment started")
    state["current_agent"] = "risk_assessment"
    
    pages = state.get("pages", [])
    compliance_result = state.get("compliance_result", "")
    
    print(f"      Assessing risk based on {len(pages)} pages...")
    print(f"      Compliance input: {compliance_result[:50]}...")
    
    if not pages:
        print("   ❌ Error: No pages available")
        return set_error(state, "risk_assessment", "No pages available for risk assessment")
    
    await asyncio.sleep(0.1)
    
    text = " ".join(pages).lower()
    
    # Calculate risk scores
    high_risk_count = sum(1 for kw in RISK_KEYWORDS['high'] if kw in text)
    medium_risk_count = sum(1 for kw in RISK_KEYWORDS['medium'] if kw in text)
    low_risk_count = sum(1 for kw in RISK_KEYWORDS['low'] if kw in text)
    
    print(f"      → High-risk indicators: {high_risk_count}")
    print(f"      → Medium-risk indicators: {medium_risk_count}")
    print(f"      → Low-risk (positive) indicators: {low_risk_count}")
    
    compliance_has_issues = "issues found" in compliance_result.lower()
    print(f"      → Compliance issues: {compliance_has_issues}")
    
    # Determine risk level
    if high_risk_count >= 2 or compliance_has_issues:
        risk_level = "HIGH"
        risk_factors = []
        if high_risk_count:
            risk_factors.append(f"{high_risk_count} high-risk indicators")
        if compliance_has_issues:
            risk_factors.append("compliance concerns")
        details = f"Factors: {', '.join(risk_factors)}"
    elif medium_risk_count >= 3 or high_risk_count >= 1:
        risk_level = "MEDIUM"
        details = f"Found {medium_risk_count} medium-risk and {high_risk_count} high-risk indicators"
    else:
        risk_level = "LOW"
        if low_risk_count:
            details = f"Positive indicators found: {low_risk_count}"
        else:
            details = "No significant risk indicators detected"
    
    result = f"Overall risk assessment: {risk_level} risk. {details}."
    state["risk_result"] = result
    
    print(f"   ✅ Risk Level: {risk_level}")
    state = add_message(state, "risk_assessment", "Risk assessment completed")
    return state


# Legacy sync process function
def process(pages, compliance_result, send_message):
    """Legacy synchronous process function."""
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
