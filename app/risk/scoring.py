from typing import Dict

def risk_score(financial_ratios: Dict, compliance: Dict) -> Dict:
    """
    Generates an aggregated financial risk score.
    """
    score = 0
    flags = []

    if financial_ratios["debt_to_equity"] > 2:
        score += 30
        flags.append("High leverage")

    if financial_ratios["profit_margin"] < 0.05:
        score += 20
        flags.append("Low profitability")

    if compliance["score"] < 70:
        score += 30
        flags.append("Compliance risk")

    risk_level = "Low"
    if score > 50:
        risk_level = "High"
    elif score > 25:
        risk_level = "Medium"

    return {
        "risk_score": score,
        "risk_level": risk_level,
        "flags": flags
    }
