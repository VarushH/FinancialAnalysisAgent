from typing import List

def score_compliance(findings: List[dict]) -> int:
    """
    Scores compliance percentage.
    """
    if not findings:
        return 0

    passed = sum(1 for f in findings if f["passed"])
    return int((passed / len(findings)) * 100)
