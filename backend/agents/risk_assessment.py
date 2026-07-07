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
import re
from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


# --- Risk Assessment Schemas ---
class RiskRatio(BaseModel):
    """Individual financial ratio assessment for a specific period."""
    name: str = Field(description="Name of the ratio (e.g., Current Ratio)")
    period: str = Field(description="Fiscal period this ratio was computed for (e.g., FY2024)")
    value: float = Field(description="Calculated value of the ratio (NaN if unknown)")
    description: str = Field(description="Explanation of what this ratio indicates")


class RiskAnomaly(BaseModel):
    """Detected financial anomaly between two periods."""
    item: str = Field(description="Financial line item with anomaly")
    period_from: str = Field(description="Earlier period")
    period_to: str = Field(description="Later period")
    yoy_change: float = Field(description="Fractional change between the two periods")
    severity: str = Field(description="'High', 'Medium', or 'Low'")
    explanation: str = Field(description="Why this is flagged as anomalous")


class RiskAssessmentReport(BaseModel):
    """Complete risk assessment report."""
    ratios: List[RiskRatio] = Field(description="Financial ratios analyzed, per period")
    anomalies: List[RiskAnomaly] = Field(description="Detected anomalies across periods")
    risk_score: int = Field(description="Overall risk score 0-100 (higher = more risk)")
    risk_level: str = Field(description="'LOW', 'MEDIUM', or 'HIGH'")
    key_insights: List[str] = Field(description="Key risk insights and recommendations")
    periods_analyzed: List[str] = Field(default_factory=list, description="All fiscal periods detected and analyzed")


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
        self.is_df = income_statement_df.copy() if income_statement_df is not None else pd.DataFrame()
        self.bs_df = balance_sheet_df.copy() if balance_sheet_df is not None else pd.DataFrame()

        # Ratios keyed by period label: {"FY2024": {"net_margin": ..., ...}, ...}
        self.ratios = {}
        self.periods = []          # ordered period labels, most-recent first
        self.scores = {}
        self.anomalies = []
        self.insights = []

    @staticmethod
    def _detect_period_columns(df):
        """
        Scan column headers and return [(year, col_name), ...] most-recent first.
        Extracts a 4-digit year from ANY header text ('FY2024', '2024', 'Dec 2024').
        This is what makes the engine year-agnostic instead of assuming 'FY2024'.
        """
        if df is None or df.empty:
            return []
        detected = []
        for col in df.columns:
            m = re.search(r'(19|20)\d{2}', str(col))
            if m:
                detected.append((int(m.group()), col))
        seen, ordered = set(), []
        for year, col in sorted(detected, key=lambda x: x[0], reverse=True):
            if year not in seen:
                seen.add(year)
                ordered.append((year, col))
        return ordered

    def _get_val(self, df, row_pattern, col_name):
        """Extract a numeric value for a row pattern from a specific column. NaN if absent."""
        if df.empty or col_name not in df.columns:
            return float('nan')
        mask = df.iloc[:, 0].astype(str).str.contains(row_pattern, case=False, na=False)
        result = df.loc[mask, col_name]
        if not result.empty:
            val_str = str(result.values[0]).replace(',', '').replace('$', '').strip()
            try:
                return float(val_str)
            except ValueError:
                return float('nan')
        return float('nan')

    def calculate_ratios(self):
        """Compute ratios for EVERY detected period, keyed by period label."""
        is_periods = dict((y, c) for y, c in self._detect_period_columns(self.is_df))
        bs_periods = dict((y, c) for y, c in self._detect_period_columns(self.bs_df))
        all_years = sorted(set(is_periods) | set(bs_periods), reverse=True)

        for year in all_years:
            label = f"FY{year}"
            is_col = is_periods.get(year)
            bs_col = bs_periods.get(year)
            r = {"net_margin": float('nan'), "gross_margin": float('nan'),
                 "debt_to_equity": float('nan'), "current_ratio": float('nan')}

            if is_col:
                rev = self._get_val(self.is_df, 'Revenue', is_col)
                ni = self._get_val(self.is_df, 'Net Income', is_col)
                gp = self._get_val(self.is_df, 'Gross Profit', is_col)
                if rev and rev > 0:
                    r["net_margin"] = ni / rev
                    r["gross_margin"] = gp / rev

            if bs_col:
                total_liab = self._get_val(self.bs_df, 'Total Liabilities', bs_col)
                total_equity = self._get_val(self.bs_df, 'Total Equity', bs_col)
                current_assets = self._get_val(self.bs_df, 'Current Assets', bs_col)
                current_liab = self._get_val(self.bs_df, 'Current Liabilities', bs_col)
                if total_equity and total_equity > 0:
                    r["debt_to_equity"] = total_liab / total_equity
                if current_liab and current_liab > 0:
                    r["current_ratio"] = current_assets / current_liab

            self.ratios[label] = r
            self.periods.append(label)

    def detect_anomalies(self) -> List[Dict]:
        """Detect >20% swings between each pair of consecutive detected periods."""
        periods = self._detect_period_columns(self.is_df)  # (year, col) desc
        if self.is_df.empty or len(periods) < 2:
            self.anomalies = []
            return []

        anomaly_list = []
        for i in range(len(periods) - 1):
            new_year, new_col = periods[i]
            old_year, old_col = periods[i + 1]
            new_vals = pd.to_numeric(self.is_df[new_col].astype(str).str.replace(',', ''), errors='coerce')
            old_vals = pd.to_numeric(self.is_df[old_col].astype(str).str.replace(',', ''), errors='coerce')

            for idx in self.is_df.index:
                old_v, new_v = old_vals.get(idx), new_vals.get(idx)
                if pd.notna(old_v) and pd.notna(new_v) and old_v != 0:
                    yoy = (new_v - old_v) / abs(old_v)
                    if abs(yoy) > 0.20:
                        item_name = str(self.is_df.iloc[idx, 0])
                        severity = "High" if abs(yoy) > 0.50 else "Medium" if abs(yoy) > 0.30 else "Low"
                        anomaly_list.append({
                            "item": item_name,
                            "period_from": f"FY{old_year}",
                            "period_to": f"FY{new_year}",
                            "yoy_change": yoy,
                            "severity": severity,
                            "explanation": f"{'+' if yoy > 0 else ''}{yoy:.1%} change FY{old_year}\u2192FY{new_year}"
                        })
        self.anomalies = anomaly_list
        return anomaly_list

    def generate_risk_score(self) -> int:
        """Score from the MOST RECENT period's ratios + anomalies across all periods."""
        import math
        score = 0
        latest = self.periods[0] if self.periods else None
        latest_ratios = self.ratios.get(latest, {}) if latest else {}

        current_ratio = latest_ratios.get('current_ratio', float('nan'))
        debt_to_equity = latest_ratios.get('debt_to_equity', float('nan'))

        if not math.isnan(current_ratio) and current_ratio < 1.0:
            score += 40
            self.insights.append(f"Liquidity concern ({latest}): current ratio below 1.0 indicates short-term payment risk")

        if not math.isnan(debt_to_equity) and debt_to_equity > 2.0:
            score += 30
            self.insights.append(f"Leverage concern ({latest}): debt-to-equity above 2.0 indicates high leverage")

        high = sum(1 for a in self.anomalies if a.get('severity') == 'High')
        medium = sum(1 for a in self.anomalies if a.get('severity') == 'Medium')
        score += high * 15 + medium * 5
        if high:
            self.insights.append(f"Volatility concern: {high} high-severity swings detected across periods")

        self.scores['total_risk_score'] = min(score, 100)
        return self.scores['total_risk_score']

    def generate_report(self) -> Optional[RiskAssessmentReport]:
        """Generate the complete multi-period risk assessment report."""
        self.calculate_ratios()
        self.detect_anomalies()
        risk_score = self.generate_risk_score()

        risk_level = "HIGH" if risk_score >= 60 else "MEDIUM" if risk_score >= 30 else "LOW"

        ratio_descriptions = {
            "current_ratio": "Short-term liquidity (Current Assets / Current Liabilities)",
            "debt_to_equity": "Financial leverage (Total Liabilities / Total Equity)",
            "net_margin": "Profitability (Net Income / Revenue)",
            "gross_margin": "Production efficiency (Gross Profit / Revenue)"
        }

        ratio_reports = []
        for period in self.periods:
            for name, value in self.ratios[period].items():
                ratio_reports.append(RiskRatio(
                    name=name.replace('_', ' ').title(),
                    period=period,
                    value=value if not (isinstance(value, float) and value != value) else float('nan'),
                    description=ratio_descriptions.get(name, "")
                ))

        anomaly_reports = [
            RiskAnomaly(
                item=a['item'],
                period_from=a['period_from'],
                period_to=a['period_to'],
                yoy_change=round(a['yoy_change'], 4),
                severity=a['severity'],
                explanation=a['explanation']
            ) for a in self.anomalies[:10]
        ]

        return RiskAssessmentReport(
            ratios=ratio_reports,
            anomalies=anomaly_reports,
            risk_score=risk_score,
            risk_level=risk_level,
            key_insights=self.insights[:5],
            periods_analyzed=self.periods
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

def latest_ratios_from_tables(tables: List) -> Dict[str, Any]:
    """
    Compute the MOST RECENT period's key ratios from raw tables, reusing the same
    RiskAssessmentEngine the Risk agent uses.

    Shared on purpose: the Compliance agent's quantitative checks and the Risk
    section both call this, so their liquidity/leverage numbers are guaranteed
    to agree instead of being computed two different ways.
    """
    income_df, balance_df = None, None
    for table in tables:
        if isinstance(table, dict):
            df = pd.DataFrame(table)
        elif isinstance(table, pd.DataFrame):
            df = table
        else:
            continue
        if len(df.columns) > 0:
            first_col = ' '.join(df.iloc[:, 0].astype(str).str.lower())
            if any(kw in first_col for kw in ['revenue', 'net income', 'gross profit', 'operating']):
                income_df = df
            elif any(kw in first_col for kw in ['assets', 'liabilities', 'equity', 'current']):
                balance_df = df

    engine = RiskAssessmentEngine(income_df, balance_df)
    engine.calculate_ratios()
    latest = engine.periods[0] if engine.periods else None
    r = engine.ratios.get(latest, {}) if latest else {}
    return {
        "current_ratio": r.get("current_ratio", float('nan')),
        "debt_to_equity": r.get("debt_to_equity", float('nan')),
        "period": latest,
    }

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
            "key_insights": risk_report.key_insights,
            "periods_analyzed": risk_report.periods_analyzed
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
