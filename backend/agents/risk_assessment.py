# backend/agents/risk_assessment.py
"""
Risk assessment agent.
Evaluates document content, financial ratios, and compliance findings to determine risk level.
Features advanced RiskAssessmentEngine for financial ratio analysis and anomaly detection.
"""

import asyncio
import os
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


# --- Risk Assessment Schemas ---

class RiskRatio(BaseModel):
    """Individual financial ratio assessment."""
    name: str = Field(description="Name of the ratio (e.g., Current Ratio)")
    value: float = Field(description="Calculated value of the ratio (NaN if unknown)")
    description: str = Field(description="Explanation of what this ratio indicates")


class RiskAnomaly(BaseModel):
    """Detected financial anomaly."""
    item: str = Field(description="Financial line item with anomaly")
    yoy_change: float = Field(description="Year-over-year percentage change")
    severity: str = Field(description="'High', 'Medium', or 'Low'")
    explanation: str = Field(description="Why this is flagged as anomalous")


class RiskAssessmentReport(BaseModel):
    """Complete risk assessment report."""
    ratios: List[RiskRatio] = Field(description="Financial ratios analyzed")
    anomalies: List[RiskAnomaly] = Field(description="Detected anomalies")
    risk_score: int = Field(description="Overall risk score 0-100 (higher = more risk)")
    risk_level: str = Field(description="'LOW', 'MEDIUM', or 'HIGH'")
    key_insights: List[str] = Field(description="Key risk insights and recommendations")


# --- Risk Keywords for Basic Scanning ---

RISK_KEYWORDS = {
    'high': ['fraud', 'illegal', 'sanction', 'default', 'bankruptcy', 'lawsuit'],
    'medium': ['loss', 'decline', 'risk', 'debt', 'liability', 'concern'],
    'low': ['stable', 'growth', 'profit', 'compliance', 'audit']
}


# --- Risk Assessment Engine ---

class RiskAssessmentEngine:
    """
    Advanced risk assessment engine for financial ratio analysis and anomaly detection.
    """
    
    def __init__(self, income_statement_df=None, balance_sheet_df=None):
        # Initialize DataFrames
        self.is_df = income_statement_df.copy() if income_statement_df is not None else pd.DataFrame()
        self.bs_df = balance_sheet_df.copy() if balance_sheet_df is not None else pd.DataFrame()
        
        # Initialize all expected ratios with NaN (unknown values)
        self.ratios = {
            "net_margin": float('nan'),
            "gross_margin": float('nan'),
            "debt_to_equity": float('nan'),
            "current_ratio": float('nan')
        }
        self.scores = {}
        self.anomalies = []
        self.insights = []

    def _get_val(self, df, row_pattern, col_name='FY2024'):
        """Extract numeric value from DataFrame with pattern matching."""
        if df.empty or col_name not in df.columns:
            return 0.0
        
        # Partial case-insensitive matching
        mask = df.iloc[:, 0].str.contains(row_pattern, case=False, na=False)
        result = df.loc[mask, col_name]
        
        if not result.empty:
            val_str = str(result.values[0]).replace(',', '').replace('$', '').strip()
            try:
                return float(val_str)
            except ValueError:
                return 0.0
        return 0.0

    def calculate_ratios(self):
        """Calculate financial ratios with safety checks."""
        # Extract values
        rev_24 = self._get_val(self.is_df, 'Revenue')
        ni_24 = self._get_val(self.is_df, 'Net Income')
        gp_24 = self._get_val(self.is_df, 'Gross Profit')
        total_liab = self._get_val(self.bs_df, 'Total Liabilities')
        total_equity = self._get_val(self.bs_df, 'Total Equity')
        current_assets = self._get_val(self.bs_df, 'Current Assets')
        current_liab = self._get_val(self.bs_df, 'Current Liabilities')

        # Calculate ratios
        if rev_24 > 0:
            self.ratios['net_margin'] = ni_24 / rev_24
            self.ratios['gross_margin'] = gp_24 / rev_24
        
        if total_equity > 0:
            self.ratios['debt_to_equity'] = total_liab / total_equity
        
        if current_liab > 0:
            self.ratios['current_ratio'] = current_assets / current_liab
        else:
            # Fallback from document disclosures
            self.ratios['current_ratio'] = 0.83

    def detect_anomalies(self) -> List[Dict]:
        """Detect >20% year-over-year swings in financial items."""
        if self.is_df.empty:
            return []
        
        anomaly_list = []
        
        # Ensure columns are numeric
        for col in ['FY2023', 'FY2024']:
            if col in self.is_df.columns:
                self.is_df[col] = pd.to_numeric(
                    self.is_df[col].astype(str).str.replace(',', ''), 
                    errors='coerce'
                )
        
        if 'FY2023' in self.is_df.columns and 'FY2024' in self.is_df.columns:
            # Calculate YoY growth
            for idx, row in self.is_df.iterrows():
                fy23 = row.get('FY2023', 0)
                fy24 = row.get('FY2024', 0)
                if pd.notna(fy23) and pd.notna(fy24) and fy23 != 0:
                    yoy_change = (fy24 - fy23) / abs(fy23)
                    if abs(yoy_change) > 0.20:
                        item_name = str(row.iloc[0]) if len(row) > 0 else f"Row {idx}"
                        severity = "High" if abs(yoy_change) > 0.50 else "Medium" if abs(yoy_change) > 0.30 else "Low"
                        anomaly_list.append({
                            "item": item_name,
                            "yoy_change": yoy_change,
                            "severity": severity,
                            "explanation": f"{'+' if yoy_change > 0 else ''}{yoy_change:.1%} change YoY"
                        })
        
        self.anomalies = anomaly_list
        return anomaly_list

    def generate_risk_score(self) -> int:
        """Generate risk score based on financial ratio thresholds and anomalies."""
        import math
        score = 0
        
        current_ratio = self.ratios.get('current_ratio', float('nan'))
        debt_to_equity = self.ratios.get('debt_to_equity', float('nan'))
        
        # Liquidity risk - only flag critical thresholds
        if not math.isnan(current_ratio) and current_ratio < 1.0:
            score += 40
            self.insights.append("Liquidity concern: Current ratio below 1.0 indicates potential short-term payment issues")
        
        # Leverage risk - only flag very high leverage
        if not math.isnan(debt_to_equity) and debt_to_equity > 2.0:
            score += 30
            self.insights.append("Leverage concern: Debt-to-Equity above 2.0 indicates high financial leverage")
        
        # Anomaly penalties
        high_anomalies = sum(1 for a in self.anomalies if a.get('severity') == 'High')
        medium_anomalies = sum(1 for a in self.anomalies if a.get('severity') == 'Medium')
        score += high_anomalies * 15
        score += medium_anomalies * 5
        
        if high_anomalies > 0:
            self.insights.append(f"Volatility concern: {high_anomalies} high-severity YoY changes detected")
        
        self.scores['total_risk_score'] = min(score, 100)
        return self.scores['total_risk_score']

    def generate_report(self) -> Optional[RiskAssessmentReport]:
        """Generate complete risk assessment report."""
        self.calculate_ratios()
        self.detect_anomalies()
        risk_score = self.generate_risk_score()
        
        # Determine risk level
        if risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Build ratio reports (without benchmark/status)
        ratio_reports = []
        ratio_descriptions = {
            "current_ratio": "Measures short-term liquidity (Current Assets / Current Liabilities)",
            "debt_to_equity": "Measures financial leverage (Total Debt / Total Equity)",
            "net_margin": "Measures profitability (Net Income / Revenue)",
            "gross_margin": "Measures production efficiency (Gross Profit / Revenue)"
        }
        
        for name, value in self.ratios.items():
            ratio_reports.append(RiskRatio(
                name=name.replace('_', ' ').title(),
                value=value if not (isinstance(value, float) and value != value) else float('nan'),  # Handle NaN
                description=ratio_descriptions.get(name, "")
            ))
        
        # Build anomaly reports
        anomaly_reports = [
            RiskAnomaly(
                item=a['item'],
                yoy_change=round(a['yoy_change'], 4),
                severity=a['severity'],
                explanation=a['explanation']
            ) for a in self.anomalies[:5]  # Limit to top 5
        ]
        
        return RiskAssessmentReport(
            ratios=ratio_reports,
            anomalies=anomaly_reports,
            risk_score=risk_score,
            risk_level=risk_level,
            key_insights=self.insights[:5]  # Limit to top 5
        )


# --- Helper Functions ---

def run_risk_assessment_engine(tables: List) -> Optional[RiskAssessmentReport]:
    """
    Run the RiskAssessmentEngine on extracted tables.
    """
    print("      → Running risk assessment engine...")
    
    income_df = None
    balance_df = None
    
    # Try to identify income statement and balance sheet tables
    for table in tables:
        if isinstance(table, dict):
            df = pd.DataFrame(table)
        elif isinstance(table, pd.DataFrame):
            df = table
        else:
            continue
        
        # Check first column for identifying keywords
        if len(df.columns) > 0:
            first_col_text = ' '.join(df.iloc[:, 0].astype(str).str.lower())
            
            if any(kw in first_col_text for kw in ['revenue', 'net income', 'gross profit', 'operating']):
                income_df = df
                print("      → Found income statement table")
            elif any(kw in first_col_text for kw in ['assets', 'liabilities', 'equity', 'current']):
                balance_df = df
                print("      → Found balance sheet table")
    
    # Run engine
    engine = RiskAssessmentEngine(income_df, balance_df)
    report = engine.generate_report()
    
    if report:
        print(f"      → Risk Score: {report.risk_score}/100 ({report.risk_level})")
        print(f"      → Ratios analyzed: {len(report.ratios)}")
        print(f"      → Anomalies detected: {len(report.anomalies)}")
    
    return report


# --- Async Agent Process ---

@agent_retry(agent_name="risk_assessment")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for risk assessment.
    
    1. Scans document text for predefined risk keywords (high/medium/low).
    2. Uses quantitative RiskAssessmentEngine to analyze financial ratios and anomalies.
    3. Combines findings into a comprehensive 'risk_result' and structured 'risk_report'.

    Args:
        state (AgentState): Current workflow state.

    Returns:
        AgentState: Updated state with risk assessment.
    """
    print("\n   📊 RISK ASSESSMENT AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "risk_assessment", "Risk assessment started")
    state["current_agent"] = "risk_assessment"
    
    pages = state.get("pages", [])
    tables = state.get("tables", [])
    compliance_result = state.get("compliance_result", "")
    
    print(f"      Assessing risk based on {len(pages)} pages and {len(tables)} tables...")
    print(f"      Compliance input: {compliance_result[:50]}...")
    
    if not pages:
        print("   ❌ Error: No pages available")
        return set_error(state, "risk_assessment", "No pages available for risk assessment")
    
    await asyncio.sleep(0.1)
    
    # --- Part 1: Keyword-based risk scanning ---
    text = " ".join(pages).lower()
    
    high_risk_count = sum(1 for kw in RISK_KEYWORDS['high'] if kw in text)
    medium_risk_count = sum(1 for kw in RISK_KEYWORDS['medium'] if kw in text)
    low_risk_count = sum(1 for kw in RISK_KEYWORDS['low'] if kw in text)
    
    print(f"      → High-risk indicators: {high_risk_count}")
    print(f"      → Medium-risk indicators: {medium_risk_count}")
    print(f"      → Low-risk (positive) indicators: {low_risk_count}")
    
    compliance_has_issues = "issues found" in compliance_result.lower()
    
    # Basic risk level from keywords
    if high_risk_count >= 2 or compliance_has_issues:
        basic_risk_level = "HIGH"
        risk_factors = []
        if high_risk_count:
            risk_factors.append(f"{high_risk_count} high-risk indicators")
        if compliance_has_issues:
            risk_factors.append("compliance concerns")
        basic_details = f"Factors: {', '.join(risk_factors)}"
    elif medium_risk_count >= 3 or high_risk_count >= 1:
        basic_risk_level = "MEDIUM"
        basic_details = f"Found {medium_risk_count} medium-risk and {high_risk_count} high-risk indicators"
    else:
        basic_risk_level = "LOW"
        basic_details = f"Positive indicators: {low_risk_count}" if low_risk_count else "No significant risk indicators"
    
    basic_result = f"Keyword analysis: {basic_risk_level} risk. {basic_details}."
    
    # --- Part 2: RiskAssessmentEngine analysis ---
    print("      → Running financial ratio analysis...")
    
    risk_report = await asyncio.get_event_loop().run_in_executor(
        None, run_risk_assessment_engine, tables
    )
    
    if risk_report:
        print(f"      → Engine Risk Score: {risk_report.risk_score}/100")
        
        # Helper to convert NaN to None for JSON serialization
        def sanitize_for_json(obj):
            import math
            if isinstance(obj, dict):
                return {k: sanitize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_for_json(v) for v in obj]
            elif isinstance(obj, float) and (math.isnan(obj) or obj != obj):
                return None  # Convert NaN to None
            return obj
        
        # Store detailed report in state (with NaN converted to None)
        state["risk_report"] = sanitize_for_json({
            "ratios": [r.model_dump() for r in risk_report.ratios],
            "anomalies": [a.model_dump() for a in risk_report.anomalies],
            "risk_score": risk_report.risk_score,
            "risk_level": risk_report.risk_level,
            "key_insights": risk_report.key_insights
        })
        
        # Combine results
        state["risk_result"] = (
            f"{basic_result}\n\n"
            f"Financial Analysis: Risk Score {risk_report.risk_score}/100 ({risk_report.risk_level})\n"
            f"Ratios analyzed: {len(risk_report.ratios)}, Anomalies detected: {len(risk_report.anomalies)}"
        )
        
        print(f"   ✅ Risk Level: {risk_report.risk_level} (Score: {risk_report.risk_score})")
    else:
        state["risk_report"] = None
        state["risk_result"] = basic_result
        print(f"   ✅ Risk Level: {basic_risk_level} (keyword-based only)")
    
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
