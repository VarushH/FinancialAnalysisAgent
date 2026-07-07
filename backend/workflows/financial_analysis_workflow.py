# backend/workflows/financial_analysis_workflow.py
"""
LangGraph-based supervisor workflow for financial analysis.
Features:
- Human-in-the-loop checkpoints (extraction review, report approval)
- Parallel agent execution (finance + compliance)
- State persistence with checkpointer
- WebSocket progress updates
"""

import os
import asyncio
import logging
import traceback
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from api.models import AnalysisSession
from .state import AgentState, create_initial_state, add_message
from .checkpointer import get_checkpointer, async_checkpointer, get_checkpoint_config
from .supervisor import supervisor_node, route_after_supervisor, HUMAN_CHECKPOINTS

logger = logging.getLogger(__name__)


def log_step(step_name: str, message: str):
    """Print a workflow step for terminal visibility."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {step_name}: {message}")


# --- Node Functions ---

async def document_extraction_node(state: AgentState) -> AgentState:
    """Node that performs document extraction."""
    log_step("DOC EXTRACT", "Starting...")
    from agents.document_extraction import process_async as doc_extract_async
    state = await doc_extract_async(state)
    
    pages_count = len(state.get('pages', []))
    log_step("DOC EXTRACT", f"Done - {pages_count} pages")
    return state


async def extraction_review_node(state: AgentState) -> AgentState:
    """Runs only AFTER a human approves (interrupt pauses BEFORE this node)."""
    log_step("CHECKPOINT", "✅ Extraction approved, resuming")
    state["extraction_approved"] = True
    state["requires_human_approval"] = False
    state["approval_checkpoint"] = None
    state["status"] = "processing"
    if state.get("human_feedback"):
        state = add_message(state, "human", f"Feedback: {state['human_feedback']}")
    return state


async def parallel_analysis_node(state: AgentState) -> AgentState:
    """Run finance analysis and compliance check in parallel."""
    log_step("PARALLEL", "Starting finance + compliance...")
    
    # Clear approval state
    state["requires_human_approval"] = False
    state["approval_checkpoint"] = None
    
    # Create copies for parallel execution
    finance_state = state.copy()
    compliance_state = state.copy()
    
    # Run in parallel
    from agents.finance_analysis import process_async as finance_analyze_async
    from agents.compliance import process_async as compliance_check_async
    
    finance_result, compliance_result = await asyncio.gather(
        finance_analyze_async(finance_state),
        compliance_check_async(compliance_state),
        return_exceptions=True
    )
    
    # Merge results
    if isinstance(finance_result, dict):
        state["analysis_result"] = finance_result.get("analysis_result")
        # CRITICAL: Copy extracted financial data
        state["financial_extraction"] = finance_result.get("financial_extraction")
        log_step("PARALLEL", f"Finance: {state['analysis_result'][:40]}...")
    else:
        log_step("PARALLEL", f"Finance failed: {finance_result}")
        state["analysis_result"] = "Analysis failed"
    
    if isinstance(compliance_result, dict):
        state["compliance_result"] = compliance_result.get("compliance_result")
        # CRITICAL: Also copy the audit_report from compliance agent!
        state["audit_report"] = compliance_result.get("audit_report")
        log_step("PARALLEL", f"Compliance: {state['compliance_result'][:40]}...")
        if state.get("audit_report"):
            log_step("PARALLEL", f"Audit report: Score {state['audit_report'].get('compliance_score')}/100")
        else:
            log_step("PARALLEL", "Audit report: None (LLM audit may have failed)")
    else:
        log_step("PARALLEL", f"Compliance failed: {compliance_result}")
        state["compliance_result"] = "Compliance check failed"
        state["audit_report"] = None
    
    state["current_agent"] = "parallel_analysis"
    log_step("PARALLEL", "Done")
    return state


async def risk_assessment_node(state: AgentState) -> AgentState:
    """Node that performs risk assessment."""
    log_step("RISK", "Starting...")
    from agents.risk_assessment import process_async as risk_assess_async
    state = await risk_assess_async(state)
    log_step("RISK", f"Done - {state.get('risk_result', 'N/A')[:40]}")
    return state


async def report_generation_node(state: AgentState) -> AgentState:
    """Node that generates the final report."""
    log_step("REPORT", "Generating PDF...")
    from agents.report_generation import process_async as report_generate_async
    state = await report_generate_async(state)
    
    # Debug: Check if report_path is set
    report_path = state.get('report_path')
    print(f"   📄 REPORT NODE - report_path after generation: {report_path}")
    if report_path:
        print(f"   📄 REPORT NODE - file exists: {os.path.exists(report_path)}")
    
    log_step("REPORT", f"Done - {report_path}")
    return state


async def report_approval_node(state: AgentState) -> AgentState:
    """Runs only AFTER a human approves the report (interrupt pauses BEFORE)."""
    log_step("CHECKPOINT", "✅ Report approved, finalizing")
    state["report_approved"] = True
    state["requires_human_approval"] = False
    state["approval_checkpoint"] = None
    state["status"] = "processing"
    return state


async def completion_node(state: AgentState) -> AgentState:
    """Final node marking workflow completion."""
    log_step("COMPLETE", "🎉 Workflow finished!")
    state["status"] = "completed"
    state["current_agent"] = "completed"
    state["requires_human_approval"] = False
    state["approval_checkpoint"] = None
    return state


# --- Build the Graph ---
WORKERS = ["document_extraction", "extraction_review", "parallel_analysis",
           "risk_assessment", "report_generation", "report_approval"]


def build_workflow_graph() -> StateGraph:
    """Build the supervisor-hub workflow graph."""
    print("\n📊 Building LangGraph workflow (supervisor hub)...")

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("document_extraction", document_extraction_node)
    workflow.add_node("extraction_review", extraction_review_node)
    workflow.add_node("parallel_analysis", parallel_analysis_node)
    workflow.add_node("risk_assessment", risk_assessment_node)
    workflow.add_node("report_generation", report_generation_node)
    workflow.add_node("report_approval", report_approval_node)
    workflow.add_node("completion", completion_node)

    # Supervisor is the entry point and the hub
    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges("supervisor", route_after_supervisor, {
        "document_extraction": "document_extraction",
        "extraction_review":   "extraction_review",
        "parallel_analysis":   "parallel_analysis",
        "risk_assessment":     "risk_assessment",
        "report_generation":   "report_generation",
        "report_approval":     "report_approval",
        "completion":          "completion",
        "end":                 END,
    })

    # Every worker reports back to the supervisor
    for w in WORKERS:
        workflow.add_edge(w, "supervisor")
    workflow.add_edge("completion", END)

    print("   ✅ Workflow graph built")
    return workflow


# Cache the graph builder (cheap to compile repeatedly - no I/O). The async
# pipeline compiles a fresh app per run against a fresh checkpointer/event
# loop (see checkpointer.async_checkpointer); only the sync, read-only path
# keeps a persistent compiled app since its checkpointer isn't event-loop-bound.
_workflow_graph = None
_compiled_workflow_sync = None


def get_workflow_graph() -> StateGraph:
    """Get the (uncompiled) workflow graph builder (cached)."""
    global _workflow_graph
    if _workflow_graph is None:
        _workflow_graph = build_workflow_graph()
    return _workflow_graph


def get_compiled_workflow_sync():
    """Sync-checkpointed compiled workflow (cached), used for read-only state lookups."""
    global _compiled_workflow_sync

    if _compiled_workflow_sync is not None:
        return _compiled_workflow_sync

    checkpointer = get_checkpointer()

    _compiled_workflow_sync = get_workflow_graph().compile(
        checkpointer=checkpointer,
        interrupt_before=HUMAN_CHECKPOINTS,
    )
    return _compiled_workflow_sync


def clear_workflow_cache():
    """Clear cached workflows (for testing)."""
    global _workflow_graph, _compiled_workflow_sync
    _workflow_graph = None
    _compiled_workflow_sync = None


# --- Public API ---

async def arun_analysis_pipeline(session_id: int, user_query: str = None) -> AgentState:
    """Run until the FIRST human checkpoint (interrupt pauses the graph)."""
    print(f"\n{'='*50}\nSTARTING PIPELINE - Session {session_id}\n{'='*50}")

    def get_session(sid):
        return AnalysisSession.objects.get(pk=sid)

    session = await asyncio.get_event_loop().run_in_executor(None, get_session, session_id)
    state = create_initial_state(session_id, session.file.path, user_query=user_query)

    config = get_checkpoint_config(session_id)
    try:
        async with async_checkpointer() as checkpointer:
            app = get_workflow_graph().compile(checkpointer=checkpointer, interrupt_before=HUMAN_CHECKPOINTS)
            final_state = await app.ainvoke(state, config)  # stops at first interrupt
        print(f"✅ Paused/finished - status={final_state.get('status')}, "
              f"checkpoint={final_state.get('approval_checkpoint')}")
        return final_state
    except Exception as e:
        traceback.print_exc()
        state["status"] = "failed"; state["error"] = str(e)
        return state


async def aresume_pipeline(session_id: int, feedback: str = None,
                           edited_content: dict = None) -> AgentState:
    """Resume from wherever the graph is paused. Works for BOTH checkpoints."""
    print(f"\n{'='*50}\nRESUMING PIPELINE - Session {session_id}\n{'='*50}")
    config = get_checkpoint_config(session_id)

    updates = {}
    if feedback:
        updates["human_feedback"] = feedback
    if edited_content:
        if "analysis" in edited_content:   updates["analysis_result"]   = edited_content["analysis"]
        if "compliance" in edited_content: updates["compliance_result"] = edited_content["compliance"]
        if "risk" in edited_content:       updates["risk_result"]       = edited_content["risk"]
        updates["report_path"] = None      # force clean regeneration with edited text

    try:
        async with async_checkpointer() as checkpointer:
            app = get_workflow_graph().compile(checkpointer=checkpointer, interrupt_before=HUMAN_CHECKPOINTS)
            if updates:
                await app.aupdate_state(config, updates)
            final_state = await app.ainvoke(None, config)  # None = resume from interrupt
        print(f"✅ Resume result - status={final_state.get('status')}, "
              f"checkpoint={final_state.get('approval_checkpoint')}")
        return final_state
    except Exception as e:
        traceback.print_exc()
        return {"status": "failed", "error": str(e), "session_id": session_id}


# --- Sync Wrappers ---

def run_analysis_pipeline(session_id: int, user_query: str = None):
    """Synchronous wrapper - runs until first checkpoint."""
    return async_to_sync(arun_analysis_pipeline)(session_id, user_query)


def resume_analysis_pipeline(session_id: int, feedback: str = None,
                             checkpoint: str = None, edited_content: dict = None):
    """Resume from a checkpoint. `checkpoint` kept for signature compatibility;
    routing is now automatic via the supervisor + interrupt."""
    return async_to_sync(aresume_pipeline)(session_id, feedback, edited_content)


def get_workflow_state(session_id: int):
    """Read live state straight from the checkpointer (replaces the old cache)."""
    app = get_compiled_workflow_sync()
    config = get_checkpoint_config(session_id)
    snapshot = app.get_state(config)
    return snapshot.values if snapshot else None

