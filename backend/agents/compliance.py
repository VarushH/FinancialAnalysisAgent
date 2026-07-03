# backend/agents/compliance.py
"""
Compliance checking agent.
Scans documents for compliance issues and forbidden terms.
Performs LLM-based regulatory compliance audits (IFRS, SOX 404).
"""

import asyncio
import os
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
    requirement: str
    status: str = Field(description="'Compliant', 'Non-Compliant', or 'Observation'")
    evidence: str = Field(description="Exact text snippet proving the status")


class RiskFlag(BaseModel):
    """Identified risk flag from document analysis."""
    severity: str = Field(description="High, Medium, or Low")
    risk_type: str = Field(description="e.g., Liquidity, Credit, Regulatory")
    description: str


class ComplianceReport(BaseModel):
    """Complete compliance audit report."""
    rules_check: List[ComplianceRule]
    risk_flags: List[RiskFlag]
    audit_trail: str = Field(description="Chronological log of checks performed (SOX, IFRS, etc.)")
    compliance_score: int = Field(description="A score from 0-100 based on findings")
    annotations: List[str] = Field(description="Specific suggestions for report improvement")


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
        "You are a Senior Regulatory Compliance Auditor. Analyze the document based on these rules:\n"
        "1. Check for IFRS and SOX 404 compliance statements.\n"
        "2. Flag liquidity risks (Current Ratio < 1.0) and leverage risks (Debt-to-Equity > 2.0).\n"
        "3. Identify mentions of internal controls and deficiencies.\n\n"
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
    
    # --- Part 2: LLM-based regulatory compliance audit ---
    print("      → Running LLM-based regulatory compliance audit...")
    
    # Convert table dicts back to DataFrames if needed
    import pandas as pd
    table_dfs = []
    if tables:
        for t in tables:
            if isinstance(t, dict):
                try:
                    table_dfs.append(pd.DataFrame(t))
                except:
                    pass
            elif hasattr(t, 'to_csv'):
                table_dfs.append(t)
    
    audit_report = await asyncio.get_event_loop().run_in_executor(
        None, run_compliance_audit, pages, table_dfs
    )
    
    if audit_report:
        print(f"      → Audit report received:  {audit_report}")
        print(f"      → Compliance Score: {audit_report.compliance_score}/100")
        print(f"      → Rules Checked: {len(audit_report.rules_check)}")
        print(f"      → Risk Flags: {len(audit_report.risk_flags)}")
        
        # Store detailed audit results in state
        state["audit_report"] = {
            "rules_check": [rule.model_dump() for rule in audit_report.rules_check],
            "risk_flags": [flag.model_dump() for flag in audit_report.risk_flags],
            "audit_trail": audit_report.audit_trail,
            "compliance_score": audit_report.compliance_score,
            "annotations": audit_report.annotations
        }
        
        # Update compliance result with audit summary
        state["compliance_result"] = (
            f"{basic_result}\n\n"
            f"Regulatory Audit Score: {audit_report.compliance_score}/100\n"
            f"Risk Flags: {len(audit_report.risk_flags)} identified\n"
            f"Annotations: {len(audit_report.annotations)} improvement suggestions"
        )
    else:
        print("      → LLM audit skipped (not available)")
        state["audit_report"] = None
    
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
