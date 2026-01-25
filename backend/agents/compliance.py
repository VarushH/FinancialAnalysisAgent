# backend/agents/compliance.py
"""
Compliance checking agent.
Scans documents for compliance issues and forbidden terms.
"""

import asyncio
from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry

FORBIDDEN_TERMS = [
    'fraud', 'bribery', 'kickback', 'illegal', 'sanction',
    'money laundering', 'embezzlement', 'insider trading',
    'tax evasion', 'corruption'
]


@agent_retry(agent_name="compliance")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for compliance checking.
    """
    print("\n   ⚖️  COMPLIANCE AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "compliance", "Compliance checking started")
    state["current_agent"] = "compliance"
    
    pages = state.get("pages", [])
    
    print(f"      Scanning {len(pages)} pages for compliance issues...")
    
    if not pages:
        print("   ❌ Error: No pages available")
        return set_error(state, "compliance", "No pages available for compliance check")
    
    await asyncio.sleep(0.1)
    
    # Scan for forbidden terms
    text = " ".join(pages).lower()
    found_issues = []
    
    for term in FORBIDDEN_TERMS:
        if term in text:
            found_issues.append(term)
            print(f"      ⚠️  Found: '{term}'")
    
    if found_issues:
        severity = "HIGH" if len(found_issues) >= 3 else "MEDIUM" if len(found_issues) >= 2 else "LOW"
        result = f"Potential compliance issues found ({severity} severity): {', '.join(found_issues)}."
        print(f"   ⚠️  {len(found_issues)} issues found - {severity} severity")
    else:
        result = "No immediate compliance issues detected. Document appears compliant."
        print(f"   ✅ No compliance issues detected")
    
    state["compliance_result"] = result
    state = add_message(state, "compliance", "Compliance checking completed")
    return state


# Legacy sync process function
def process(pages, send_message):
    """Legacy synchronous process function."""
    send_message("Compliance checking started")
    text = " ".join(pages).lower()
    forbidden = ['fraud', 'bribery', 'kickback', 'illegal', 'sanction']
    found = [word for word in forbidden if word in text]
    if found:
        result = f"Potential compliance issues found: {', '.join(found)}."
    else:
        result = "No immediate compliance issues detected."
    send_message("Compliance checking completed")
    return result
