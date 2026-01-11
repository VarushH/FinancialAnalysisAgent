from typing import Dict

def calculate_ratios(financials: Dict) -> Dict:
    """
    Calculates core financial ratios.
    """
    revenue = financials.get("revenue", 0)
    expenses = financials.get("expenses", 1)
    assets = financials.get("total_assets", 1)
    liabilities = financials.get("total_liabilities", 1)
    equity = financials.get("equity", 1)

    return {
        "profit_margin": round((revenue - expenses) / max(revenue, 1), 4),
        "debt_to_equity": round(liabilities / max(equity, 1), 4),
        "return_on_assets": round((revenue - expenses) / max(assets, 1), 4),
        "current_ratio": round(assets / max(liabilities, 1), 4)
    }
