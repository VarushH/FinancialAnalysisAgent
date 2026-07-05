# backend/workflows/supervisor.py
"""
Supervisor router for the financial analysis workflow.
Routing is STATE-DRIVEN: the next node is derived entirely from what already
exists in state. This is the single source of truth for the flow.
"""

import logging
from .state import AgentState, add_message

logger = logging.getLogger(__name__)

# Nodes that require human approval before proceeding
HUMAN_CHECKPOINTS = ["extraction_review", "report_approval"]


def route_next_agent(state: AgentState) -> str:
    """Decide the next node purely from what is already present in state."""
    if state.get("status") == "failed":
        return "end"

    # 1. No pages yet -> extract
    if not state.get("pages"):
        return "document_extraction"

    # 2. Pages exist but human hasn't reviewed extraction -> checkpoint
    if not state.get("extraction_approved"):
        return "extraction_review"

    # 3. Analysis + compliance not both done -> run them in parallel
    if not (state.get("analysis_result") and state.get("compliance_result")):
        return "parallel_analysis"

    # 4. Risk not done -> assess
    if not state.get("risk_result"):
        return "risk_assessment"

    # 5. Report not generated -> generate
    if not state.get("report_path"):
        return "report_generation"

    # 6. Report generated but not approved -> checkpoint
    if not state.get("report_approved"):
        return "report_approval"

    # 7. Everything done -> finalize
    if state.get("status") != "completed":
        return "completion"

    return "end"


def supervisor_node(state: AgentState) -> AgentState:
    """Central router node. Sets approval status when routing to a checkpoint."""
    nxt = route_next_agent(state)
    state["next_agent"] = nxt
    state["current_agent"] = "supervisor"

    if nxt in HUMAN_CHECKPOINTS:
        state["status"] = "awaiting_approval"
        state["approval_checkpoint"] = nxt
        state["requires_human_approval"] = True
    else:
        state["requires_human_approval"] = False
        state["approval_checkpoint"] = None
        if nxt != "end" and state.get("status") != "completed":
            state["status"] = "processing"

    state = add_message(state, "supervisor", f"Routing to: {nxt}")
    return state


def route_after_supervisor(state: AgentState) -> str:
    """Conditional-edge function: hand LangGraph the supervisor's decision."""
    return state.get("next_agent", "end")