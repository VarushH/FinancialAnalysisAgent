# backend/agents/compliance.py
"""
Compliance checking agent.
Scans documents for compliance issues and forbidden terms.
Performs LLM-based regulatory compliance audits (IFRS, SOX 404).
"""

import asyncio
import os
import math
import pandas as pd
from typing import List, Optional
from django.conf import settings
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_groq import ChatGroq
from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry

# --- Compliance Schemas ---

class ComplianceRule(BaseModel):
    """Individual compliance rule check result."""
    rule_id: str
    name: str = Field(description="Human-readable check name")
    requirement: str
    status: str = Field(description="'Compliant', 'Non-Compliant', or 'Observation'")
    evidence: str = Field(description="Exact text snippet proving the status")


class RiskFlag(BaseModel):
    """Identified risk flag from document analysis."""
    severity: str = Field(description="High, Medium, or Low")
    risk_type: str = Field(description="e.g., Liquidity, Credit, Regulatory")
    description: str


class ComplianceReport(BaseModel):
    """LLM-produced part of the audit (the 3 qualitative checks + supporting findings).
    The numeric score is computed in code from the final 5 checks, not by the LLM."""
    rules_check: List[ComplianceRule]
    risk_flags: List[RiskFlag]
    audit_trail: str = Field(description="Chronological log of checks performed (SOX, IFRS, etc.)")
    annotations: List[str] = Field(description="Specific suggestions for report improvement")


# --- The fixed 5-check compliance rubric (same every document) ---
# 3 qualitative checks (LLM-judged from text) + 2 quantitative (computed in code).
QUALITATIVE_CHECKS = [
    ("C1", "IFRS Presentation & Disclosure", "Statements presented on an IFRS basis with required disclosures."),
    ("C2", "SOX 404 Internal Controls", "Management attestation on internal control over financial reporting."),
    ("C3", "Going Concern", "Going-concern basis assessed and disclosed."),
]


# --- Forbidden Terms for Basic Scanning ---

FORBIDDEN_TERMS = [
    'fraud', 'bribery', 'kickback', 'illegal', 'sanction',
    'money laundering', 'embezzlement', 'insider trading',
    'tax evasion', 'corruption'
]


# --- LLM-based Compliance Audit ---

def _get_compliance_llm():
    """Get the LLM for compliance auditing."""
    try:
        
        api_key = settings.GROQ_API_KEY
        print(f"      → Initializing Groq LLM using settings key")
        return ChatGroq(
            model="llama-3.3-70b-versatile",  # Valid Groq model
            api_key=api_key,
            temperature=0.2,
            timeout=120,
            max_retries=2
        )
    except Exception as e:
        print(f"      → LLM initialization failed: {e}")
        return None


def run_compliance_audit(text_list: List[str], tables_list: List = None) -> Optional[ComplianceReport]:
    """
    Run LLM-based regulatory compliance audit on document content.
    
    Args:
        text_list: List of text content from document pages
        tables_list: Optional list of table DataFrames
        
    Returns:
        ComplianceReport with detailed audit findings, or None if audit fails
    """
    print("      → Starting compliance audit...")
    llm = _get_compliance_llm()
    if not llm:
        print("      → ERROR: Could not initialize LLM")
        return None
    
    parser = PydanticOutputParser(pydantic_object=ComplianceReport)
    
    # Build context from text and tables
    context = "\n".join(text_list)
    if tables_list:
        for df in tables_list:
            if hasattr(df, 'to_csv'):
                context += "\n" + df.to_csv()
    
    print(f"      → Context length: {len(context)} characters")
    
    prompt = ChatPromptTemplate.from_template(
        "You are a Senior Regulatory Compliance Auditor. Assess the document against EXACTLY these "
        "three qualitative checks and return one rules_check entry for each, using the given rule_id and name:\n"
        "  C1 | IFRS Presentation & Disclosure | statements presented on an IFRS basis with required disclosures.\n"
        "  C2 | SOX 404 Internal Controls | management attestation on internal control over financial reporting.\n"
        "  C3 | Going Concern | going-concern basis assessed and disclosed.\n"
        "For each, status is 'Compliant', 'Non-Compliant', or 'Observation'. If the document does NOT "
        "address a check, you MUST return 'Observation' with evidence 'insufficient evidence' — never fabricate a pass.\n"
        "Also return: risk_flags (liquidity/leverage/regulatory concerns you observe), a concise chronological "
        "audit_trail describing the checks you performed, and annotations (specific improvement suggestions).\n\n"
        "{format_instructions}\n"
        "Document Content:\n{context}"
    )
    
    try:
        print("      → Invoking LLM chain...")
        chain = prompt | llm | parser
        result = chain.invoke({
            "context": context, 
            "format_instructions": parser.get_format_instructions()
        })
        print("      → LLM chain completed successfully")
        return result
    except Exception as e:
        print(f"      → Compliance audit error: {type(e).__name__}: {e}")
        return None


# --- Async Agent Process ---

@agent_retry(agent_name="compliance")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for compliance checking.
    
    1. Scans document text for basic forbidden terms (fraud, bribery, etc.).
    2. Uses LLM to perform a deep regulatory compliance audit (IFRS/SOX).
    3. Updates state with 'compliance_result' and detailed 'audit_report'.

    Args:
        state (AgentState): Current workflow state.

    Returns:
        AgentState: Updated state with compliance findings.
    """
    print("\n   ⚖️  COMPLIANCE AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "compliance", "Compliance checking started")
    state["current_agent"] = "compliance"
    
    pages = state.get("pages", [])
    tables = state.get("tables", [])
    
    print(f"      Scanning {len(pages)} pages for compliance issues...")
    
    if not pages:
        print("   ❌ Error: No pages available")
        return set_error(state, "compliance", "No pages available for compliance check")
    
    await asyncio.sleep(0.1)
    
    # --- Part 1: Basic forbidden terms scanning ---
    text = " ".join(pages).lower()
    found_issues = []
    
    for term in FORBIDDEN_TERMS:
        if term in text:
            found_issues.append(term)
            print(f"      ⚠️  Found: '{term}'")
    
    if found_issues:
        severity = "HIGH" if len(found_issues) >= 3 else "MEDIUM" if len(found_issues) >= 2 else "LOW"
        basic_result = f"Potential compliance issues found ({severity} severity): {', '.join(found_issues)}."
        print(f"   ⚠️  {len(found_issues)} issues found - {severity} severity")
    else:
        basic_result = "No immediate compliance issues detected. Document appears compliant."
        print(f"   ✅ No basic compliance issues detected")
    
    state["compliance_result"] = basic_result
    
    # --- Part 2: Fixed 5-check rubric (3 LLM-judged + 2 computed) ---
    # Teaching point: use the LLM where judgment from text is needed, use code where
    # a number can be verified. The 2 computed checks reuse the RiskAssessmentEngine,
    # so they are guaranteed to agree with the Risk section.
    print("      → Running 5-check regulatory audit...")

    
    table_dfs = []
    for t in (tables or []):
        if isinstance(t, dict):
            try:
                table_dfs.append(pd.DataFrame(t))
            except Exception:
                pass
        elif hasattr(t, 'to_csv'):
            table_dfs.append(t)

    loop = asyncio.get_event_loop()

    # (a) Qualitative checks — LLM
    llm_audit = await loop.run_in_executor(None, run_compliance_audit, pages, table_dfs)

    # (b) Quantitative checks — computed via the shared engine
    from agents.risk_assessment import latest_ratios_from_tables
    ratios = await loop.run_in_executor(None, latest_ratios_from_tables, table_dfs)
    period_lbl = ratios.get("period") or "latest period"

    def _quant_check(cid, name, requirement, key, threshold, op):
        val = ratios.get(key, float('nan'))
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return {"rule_id": cid, "name": name, "requirement": requirement,
                    "status": "Observation",
                    "evidence": "Insufficient table data to compute this ratio."}
        ok = (val >= threshold) if op == ">=" else (val <= threshold)
        return {"rule_id": cid, "name": name, "requirement": requirement,
                "status": "Compliant" if ok else "Non-Compliant",
                "evidence": f"Computed value = {val:.2f} for {period_lbl}; requirement {op} {threshold}."}

    quant_checks = [
        _quant_check("C4", "Liquidity Adequacy", "Current ratio >= 1.0", "current_ratio", 1.0, ">="),
        _quant_check("C5", "Leverage & Debt Disclosure", "Debt-to-equity <= 2.0", "debt_to_equity", 2.0, "<="),
    ]

    # Assemble qualitative results (fall back to Observation if the LLM audit failed)
    if llm_audit and llm_audit.rules_check:
        qual_checks = []
        for rule in llm_audit.rules_check[:3]:
            d = rule.model_dump()
            if not d.get("name"):
                d["name"] = d.get("requirement", d.get("rule_id", "Check"))
            qual_checks.append(d)
        risk_flags = [f.model_dump() for f in llm_audit.risk_flags]
        audit_trail = llm_audit.audit_trail
        annotations = llm_audit.annotations
    else:
        qual_checks = [{"rule_id": cid, "name": name, "requirement": req,
                        "status": "Observation", "evidence": "Regulatory audit unavailable."}
                       for cid, name, req in QUALITATIVE_CHECKS]
        risk_flags, audit_trail, annotations = [], "Audit trail unavailable.", []

    all_checks = qual_checks + quant_checks

    # Transparent score straight from the 5 checks (reconciles the two signals)
    pts = {"Compliant": 20, "Observation": 10, "Non-Compliant": 0}
    compliance_score = sum(pts.get(c["status"], 0) for c in all_checks)

    n_compliant = sum(1 for c in all_checks if c["status"] == "Compliant")
    observations = [c for c in all_checks if c["status"] == "Observation"]
    non_compliant = [c for c in all_checks if c["status"] == "Non-Compliant"]

    # The forbidden-term scan escalates the verdict regardless of the checks
    if found_issues:
        overall = "NON-COMPLIANT"
        risk_flags = [{"severity": "High", "risk_type": "Integrity",
                       "description": f"Forbidden terms present: {', '.join(found_issues)}"}] + risk_flags
        compliance_score = min(compliance_score, 40)
    elif non_compliant:
        overall = "NON-COMPLIANT"
    elif observations:
        overall = "NEEDS REVIEW"
    else:
        overall = "COMPLIANT"

    state["audit_report"] = {
        "rules_check": all_checks,
        "risk_flags": risk_flags,
        "audit_trail": audit_trail,
        "compliance_score": compliance_score,
        "annotations": annotations,
        "overall_status": overall,
    }

    top_flags = "; ".join(f"[{f.get('severity')}] {f.get('risk_type')}" for f in risk_flags[:3]) or "none"
    top_rec = annotations[0] if annotations else "none"
    scan_txt = f"flagged: {', '.join(found_issues)}" if found_issues else "clean"
    state["compliance_result"] = (
        f"Compliance Status: {overall} - Regulatory Score {compliance_score}/100; "
        f"forbidden-term scan {scan_txt}.\n"
        f"Checks: {n_compliant}/5 compliant, {len(observations)} observation(s), {len(non_compliant)} non-compliant.\n"
        f"Top risk flags: {top_flags}.\n"
        f"Key recommendation: {top_rec}."
    )

    print(f"   ✅ Compliance verdict: {overall} ({compliance_score}/100)")
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
