from typing import Dict, List

REGULATORY_RULES = [
    {
        "id": "REV_DISCLOSURE",
        "description": "Revenue must be disclosed and non-zero",
        "check": lambda d: d.get("revenue", 0) > 0
    },
    {
        "id": "AUDIT_STATEMENT",
        "description": "Audit statement must be present",
        "check": lambda d: "audit_opinion" in d
    },
    {
        "id": "LIABILITY_REPORTING",
        "description": "Total liabilities must be reported",
        "check": lambda d: d.get("total_liabilities") is not None
    }
]

def check_rules(financials: Dict) -> List[Dict]:
    """
    Executes compliance checks.
    """
    results = []

    for rule in REGULATORY_RULES:
        passed = rule["check"](financials)
        results.append({
            "rule_id": rule["id"],
            "description": rule["description"],
            "passed": passed
        })

    return results
