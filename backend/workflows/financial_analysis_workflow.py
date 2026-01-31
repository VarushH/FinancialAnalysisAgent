# backend/workflows/financial_analysis_workflow.py
"""
LangGraph-based supervisor workflow for financial analysis.
Features:
- Human-in-the-loop checkpoints (extraction review, report approval)
- Parallel agent execution (finance + compliance)
- State persistence with checkpointer
- WebSocket progress updates
"""

import asyncio
import logging
from typing import Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from api.models import AnalysisSession
from .state import AgentState, create_initial_state, add_message
from .checkpointer import get_checkpointer, get_checkpoint_config, save_state_for_preview

# ... (imports removed)
# Import async agent functions - MOVED TO INSIDE NODES TO AVOID CIRCULAR IMPORTS
# from agents.document_extraction import process_async as doc_extract_async
# from agents.finance_analysis import process_async as finance_analyze_async
# from agents.compliance import process_async as compliance_check_async
# from agents.risk_assessment import process_async as risk_assess_async
# from agents.report_generation import process_async as report_generate_async

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
    
    # Mark that next step requires human approval
    state["pending_checkpoint"] = "extraction_review"
    return state


async def extraction_checkpoint_node(state: AgentState) -> AgentState:
    """Human checkpoint after extraction."""
    log_step("CHECKPOINT", "⏸️ Extraction review - waiting for approval")
    state["current_agent"] = "extraction_review"
    state["requires_human_approval"] = True
    state["approval_checkpoint"] = "extraction_review"
    state["status"] = "awaiting_approval"
    
    # Save state to cache for preview access
    save_state_for_preview(state.get("session_id"), state)
    
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
        import os
        print(f"   📄 REPORT NODE - file exists: {os.path.exists(report_path)}")
    
    log_step("REPORT", f"Done - {report_path}")
    
    # Mark that next step requires human approval
    state["pending_checkpoint"] = "report_approval"
    return state


async def report_checkpoint_node(state: AgentState) -> AgentState:
    """Human checkpoint for final report approval."""
    log_step("CHECKPOINT", "⏸️ Report approval - waiting for approval")
    state["current_agent"] = "report_approval"
    state["requires_human_approval"] = True
    state["approval_checkpoint"] = "report_approval"
    state["status"] = "awaiting_approval"
    
    # Save state to cache for preview access
    save_state_for_preview(state.get("session_id"), state)
    
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

def build_workflow_graph() -> StateGraph:
    """Build and return the LangGraph workflow."""
    print("\n📊 Building LangGraph workflow...")
    
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("document_extraction", document_extraction_node)
    workflow.add_node("extraction_checkpoint", extraction_checkpoint_node)
    workflow.add_node("parallel_analysis", parallel_analysis_node)
    workflow.add_node("risk_assessment", risk_assessment_node)
    workflow.add_node("report_generation", report_generation_node)
    workflow.add_node("report_checkpoint", report_checkpoint_node)
    workflow.add_node("completion", completion_node)
    
    # Set entry point
    workflow.set_entry_point("document_extraction")
    
    # Connect the nodes
    workflow.add_edge("document_extraction", "extraction_checkpoint")
    workflow.add_edge("extraction_checkpoint", END)  # Pause for approval
    
    # After resuming from extraction checkpoint:
    workflow.add_edge("parallel_analysis", "risk_assessment")
    workflow.add_edge("risk_assessment", "report_generation")
    workflow.add_edge("report_generation", "report_checkpoint")
    workflow.add_edge("report_checkpoint", END)  # Pause for approval
    
    # After resuming from report checkpoint:
    workflow.add_edge("completion", END)
    
    print("   ✅ Workflow graph built")
    return workflow


# Cache the compiled workflow
_compiled_workflow = None


def get_compiled_workflow():
    """Get the compiled workflow (cached)."""
    global _compiled_workflow
    
    if _compiled_workflow is not None:
        return _compiled_workflow
    
    workflow = build_workflow_graph()
    checkpointer = get_checkpointer()
    
    print("   ✅ Workflow compiled")
    _compiled_workflow = workflow.compile(checkpointer=checkpointer)
    return _compiled_workflow


def clear_workflow_cache():
    """Clear cached workflow (for testing)."""
    global _compiled_workflow
    _compiled_workflow = None


# --- Public API ---

async def arun_analysis_pipeline(session_id: int, user_query: str = None) -> AgentState:
    """Run the analysis pipeline - first phase until extraction checkpoint."""
    print(f"\n{'='*50}")
    print(f"STARTING PIPELINE - Session {session_id}")
    if user_query:
        print(f"USER QUERY: {user_query}")
    print(f"{'='*50}")
    
    # Get session
    def get_session(sid):
        from api.models import AnalysisSession
        return AnalysisSession.objects.get(pk=sid)
    
    session = await asyncio.get_event_loop().run_in_executor(None, get_session, session_id)
    print(f"File: {session.file.path}")
    
    # Create initial state
    state = create_initial_state(session_id, session.file.path, user_query=user_query)
    
    # Get compiled workflow
    app = get_compiled_workflow()
    config = get_checkpoint_config(session_id)
    
    # Run until first checkpoint
    try:
        print("\n🚀 Running workflow phase 1...")
        final_state = await app.ainvoke(state, config)
        print(f"\n✅ Phase 1 complete - Status: {final_state.get('status')}")
        print(f"   Requires approval: {final_state.get('requires_human_approval')}")
        print(f"   Checkpoint: {final_state.get('approval_checkpoint')}")
        return final_state
    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {e}")
        import traceback
        traceback.print_exc()
        state["status"] = "failed"
        state["error"] = str(e)
        return state


# ... (rest of the file)


# --- Sync Wrappers ---

def run_analysis_pipeline(session_id: int, user_query: str = None):
    """Synchronous wrapper - runs phase 1."""
    return async_to_sync(arun_analysis_pipeline)(session_id, user_query)


async def aresume_from_extraction(session_id: int, feedback: str = None) -> AgentState:
    """Resume from extraction checkpoint to report checkpoint."""
    print(f"\n{'='*50}")
    print(f"RESUMING PIPELINE (Phase 2) - Session {session_id}")
    print(f"{'='*50}")
    
    # Get session to get file path
    def get_session(sid):
        from api.models import AnalysisSession
        return AnalysisSession.objects.get(pk=sid)
    
    session = await asyncio.get_event_loop().run_in_executor(None, get_session, session_id)
    
    # Get the checkpointer to retrieve state
    checkpointer = get_checkpointer()
    config = get_checkpoint_config(session_id)
    
    # Try to get existing state
    try:
        checkpoint_data = checkpointer.get(config)
        if checkpoint_data and "channel_values" in checkpoint_data:
            state = checkpoint_data["channel_values"]
            print(f"   Restored state from checkpoint")
        else:
            # Create fresh state with existing data
            state = create_initial_state(session_id, session.file.path)
            # Re-run extraction to get pages
            state = await doc_extract_async(state)
            print(f"   Re-extracted document")
    except:
        state = create_initial_state(session_id, session.file.path)
        state = await doc_extract_async(state)
        print(f"   Re-extracted document (no checkpoint)")
    
    if feedback:
        state["human_feedback"] = feedback
        print(f"   Feedback: {feedback}")
    
    # Run phase 2: parallel analysis -> risk -> report -> checkpoint
    try:
        print("\n🚀 Running workflow phase 2...")
        state = await parallel_analysis_node(state)
        state = await risk_assessment_node(state)
        state = await report_generation_node(state)
        state = await report_checkpoint_node(state)
        
        # State is already saved to cache in report_checkpoint_node via save_state_for_preview
        
        print(f"\n✅ Phase 2 complete - Status: {state.get('status')}")
        return state
    except Exception as e:
        print(f"\n❌ Phase 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        state["status"] = "failed"
        state["error"] = str(e)
        return state


async def aresume_from_report(session_id: int, feedback: str = None, edited_content: dict = None) -> AgentState:
    """Resume from report checkpoint to completion."""
    print(f"\n{'='*50}")
    print(f"RESUMING PIPELINE (Phase 3) - Session {session_id}")
    print(f"{'='*50}")
    
    # Get session
    # Get session
    def get_session(sid):
        from api.models import AnalysisSession
        return AnalysisSession.objects.get(pk=sid)
    
    session = await asyncio.get_event_loop().run_in_executor(None, get_session, session_id)
    
    # Get checkpointer state - try cache first (contains report_path)
    from .checkpointer import get_cached_state
    cached_state = get_cached_state(session_id)
    
    print(f"   📦 Cached state exists: {cached_state is not None}")
    if cached_state:
        print(f"   📦 Cached state keys: {list(cached_state.keys())}")
        print(f"   📦 Cached report_path: {cached_state.get('report_path')}")
    
    if cached_state and cached_state.get('report_path'):
        state = cached_state.copy()
        print(f"   ✅ Restored state from cache (report_path: {state.get('report_path')})")
    else:
        print(f"   ⚠️ Cache miss or no report_path, trying checkpointer...")
        # Fall back to checkpointer
        checkpointer = get_checkpointer()
        config = get_checkpoint_config(session_id)
        
        try:
            checkpoint_data = checkpointer.get(config)
            if checkpoint_data and "channel_values" in checkpoint_data:
                state = checkpoint_data["channel_values"]
                print(f"   Restored state from checkpoint (report_path: {state.get('report_path')})")
            else:
                # Minimal state for completion
                state = create_initial_state(session_id, session.file.path)
                state["status"] = "completing"
                print(f"   ⚠️ No checkpoint data, created minimal state")
        except Exception as e:
            print(f"   ❌ Checkpoint retrieval failed: {e}")
            state = create_initial_state(session_id, session.file.path)
            state["status"] = "completing"
    
    if feedback:
        state["human_feedback"] = feedback
    
    # If edited content provided, update state and regenerate PDF
    if edited_content:
        print(f"   📝 Applying edited content...")
        print(f"   📝 Edited content keys: {list(edited_content.keys())}")
        if 'analysis' in edited_content:
            print(f"   📝 New analysis (first 50 chars): {edited_content['analysis'][:50]}...")
            state['analysis_result'] = edited_content['analysis']
        if 'compliance' in edited_content:
            print(f"   📝 New compliance (first 50 chars): {edited_content['compliance'][:50]}...")
            state['compliance_result'] = edited_content['compliance']
        if 'risk' in edited_content:
            print(f"   📝 New risk (first 50 chars): {edited_content['risk'][:50]}...")
            state['risk_result'] = edited_content['risk']
        
        # Regenerate PDF with edited content
        print(f"   🔄 Regenerating PDF with edited content...")
        state = await report_generation_node(state)
        print(f"   ✅ PDF regenerated: {state.get('report_path')}")
        
        # Update report_path in database immediately using executor
        report_path = state.get('report_path')
        if report_path:
            def update_report_path(sid, path):
                from api.models import AnalysisSession
                AnalysisSession.objects.filter(pk=sid).update(report_file=path)
            
            await asyncio.get_event_loop().run_in_executor(None, update_report_path, session_id, report_path)
            print(f"   💾 Report path saved to database: {report_path}")
    
    # Run phase 3: completion
    try:
        print("\n🚀 Running workflow phase 3...")
        state = await completion_node(state)
        print(f"\n✅ Phase 3 complete - Status: {state.get('status')}")
        return state
    except Exception as e:
        print(f"\n❌ Phase 3 FAILED: {e}")
        state["status"] = "failed"
        state["error"] = str(e)
        return state





def resume_analysis_pipeline(session_id: int, feedback: str = None, checkpoint: str = None, edited_content: dict = None):
    """Resume pipeline from a checkpoint."""
    if checkpoint == "extraction_review":
        return async_to_sync(aresume_from_extraction)(session_id, feedback)
    elif checkpoint == "report_approval":
        return async_to_sync(aresume_from_report)(session_id, feedback, edited_content)
    else:
        # Auto-detect based on session state
        session = AnalysisSession.objects.get(pk=session_id)
        if session.approval_checkpoint == "extraction_review":
            return async_to_sync(aresume_from_extraction)(session_id, feedback)
        else:
            return async_to_sync(aresume_from_report)(session_id, feedback, edited_content)


def get_workflow_state(session_id: int):
    """Get current workflow state from cache."""
    from .checkpointer import get_cached_state
    return get_cached_state(session_id)
