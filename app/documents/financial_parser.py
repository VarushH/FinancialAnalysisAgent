from typing import List, Dict
import re

def parse_financials(tables: List[Dict]) -> Dict:
    """
    Parses extracted tables into normalized financial fields.
    """
    data = {}

    for t in tables:
        for row in t["table"]:
            if not row or len(row) < 2:
                continue

            key = row[0].lower()
            value = row[1]

            if "revenue" in key:
                data["revenue"] = extract_number(value)
            elif "expense" in key:
                data["expenses"] = extract_number(value)
            elif "asset" in key:
                data["total_assets"] = extract_number(value)
            elif "liabilit" in key:
                data["total_liabilities"] = extract_number(value)
            elif "equity" in key:
                data["equity"] = extract_number(value)
            elif "audit" in key:
                data["audit_opinion"] = value

    return data


def extract_number(text: str) -> float:
    """
    Extracts numeric values from strings.
    """
    if not text:
        return 0.0

    numbers = re.findall(r"[\d,]+\.?\d*", text)
    return float(numbers[0].replace(",", "")) if numbers else 0.0
