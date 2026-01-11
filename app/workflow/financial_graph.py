# app/workflows/financial_graph.py
from langgraph.graph import StateGraph
from app.agents import (
    supervisor, extractor, analyzer,
    compliance, risk, report
)

graph = StateGraph(dict)

graph.add_node("supervisor", supervisor)
graph.add_node("extract", extractor.extract_agent)
graph.add_node("analyze", analyzer.analyzer_agent)
graph.add_node("compliance", compliance.compliance_agent)
graph.add_node("risk", risk.risk_agent)
graph.add_node("report", report.report_agent)

graph.set_entry_point("supervisor")

graph.add_conditional_edges(
    "supervisor",
    supervisor,
    {
        "extract": "extract",
        "analyze": "analyze",
        "compliance": "compliance",
        "risk": "risk",
        "report": "report",
        "human_approval": None
    }
)

financial_graph = graph.compile()
