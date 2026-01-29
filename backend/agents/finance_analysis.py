# backend/agents/finance_analysis.py
"""
Finance analysis agent.
Analyzes document content for financial insights.
"""

import asyncio
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


# NEW: Pydantic models for extraction
class SignificantDate(BaseModel):
    date: str = Field(description="The date or fiscal period (e.g., FY2024, 2023)")
    significance: str = Field(description="Why this date is important (e.g., Revenue peak, report end date)")

class FinancialSummary(BaseModel):
    revenue_2024: str = Field(description="The total revenue for FY2024")
    net_income_2024: str = Field(description="The net income for FY2024")
    total_assets: str = Field(description="Total assets from the balance sheet")
    total_liabilities: str = Field(description="Total liabilities from the balance sheet")
    total_equity: str = Field(description="Total shareholder's equity")
    debt_to_equity: str = Field(description="The debt-to-equity ratio")

class ExtractionResult(BaseModel):
    companies: List[str] = Field(description="List of all company names mentioned")
    currencies: List[str] = Field(description="List of currency values (e.g., USD 120M)")
    numbers: List[str] = Field(description="Significant non-currency numbers or ratios")
    important_dates: List[SignificantDate] = Field(description="List of dates and their context")
    financial_summary: FinancialSummary

# Setup LLM and Parser
parser = PydanticOutputParser(pydantic_object=ExtractionResult)
# Note: In a real production environment, API keys should be in settings/env vars.
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key="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",
    temperature=0.2,
    timeout=None,
    max_retries=2
)

def extract_with_llm(text_list, tables_list_dicts):
    """
    Extract structured financial data using LLM.
    tables_list_dicts is a list of dicts (converted from dfs previously), needs reconstruction to CSV for context.
    """
    # Combine text
    combined_content = "\n".join(text_list[:10]) # Limit to first 10 pages to avoid token limits if very large
    
    # Process tables (tables are stored as dicts in state)
    for t_dict in tables_list_dicts:
        try:
            df = pd.DataFrame.from_dict(t_dict)
            combined_content += "\n" + df.to_csv(index=False)
        except Exception:
            pass

    prompt = ChatPromptTemplate.from_template(
        "Extract specific financial data from the following document content.\n"
        "{format_instructions}\n"
        "Content:\n{context}"
        """Instructions: 
             1. Currency extracted should not have numbers, it shuold have the unique currency types available in the document
             2. Number extracted must have significance written along for better interpreation of result
             3. The dates should be extracted only if it has proper format written in Date,Month,Year format along with tis significance.
        """
    )

    chain = prompt | llm | parser

    try:
        return chain.invoke({
            "context": combined_content[:50000], # Hard cap context char count
            "format_instructions": parser.get_format_instructions()
        })
    except Exception as e:
        print(f"      Running extraction failed: {e}")
        return None


@agent_retry(agent_name="finance_analysis")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for finance analysis.
    """
    print("\n   💰 FINANCE ANALYSIS AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "finance_analysis", "Finance analysis started")
    state["current_agent"] = "finance_analysis"
    
    pages = state.get("pages", [])
    tables = state.get("tables", [])
    
    print(f"      Analyzing {len(pages)} pages and {len(tables)} tables...")
    
    if not pages:
        print("   ❌ Error: No pages available")
        return set_error(state, "finance_analysis", "No pages available for analysis")
    
    # Run LLM Extraction in thread pool
    print("      → Running LLM extraction...")
    loop = asyncio.get_event_loop()
    extraction_result = await loop.run_in_executor(None, extract_with_llm, pages, tables)
    
    if extraction_result:
        print("      ✅ LLM Extraction successful")
        # Store as dict for serialization
        state["financial_extraction"] = extraction_result.dict()
        
        # Create a summary string for the legacy analysis field
        fs = extraction_result.financial_summary
        analysis_summary = (
            f"Financial Summary for FY2024: Revenue {fs.revenue_2024}, "
            f"Net Income {fs.net_income_2024}, Assets {fs.total_assets}. "
            f"Key extracted data includes {len(extraction_result.important_dates)} significant dates "
            f"and {len(extraction_result.numbers)} key ratios."
        )
        state["analysis_result"] = analysis_summary
    else:
        print("      ⚠️ LLM Extraction returned no result, falling back to basic analysis")
        state["analysis_result"] = "Basic analysis: Document contains financial data but automated extraction failed."
    
    # Legacy logic as fallback/augment
    # ... (simplified)
    
    print(f"   ✅ Analysis complete.")
    state = add_message(state, "finance_analysis", "Finance analysis completed")
    return state


# Legacy sync process function
def process(pages, tables, send_message):
    """Legacy synchronous process function."""
    send_message("Finance analysis started")
    # For legacy sync calls, we just return a dummy string to avoid breaking old callers
    analysis = "Legacy process called. Please use async process for full extraction."
    send_message("Finance analysis completed")
    return analysis
 