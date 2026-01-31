# backend/workflows/state.py
"""
State management for the supervisor agent workflow.
Defines the shared state structure used across all agents.
"""

from typing import TypedDict, Optional, List, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime


class AgentState(TypedDict, total=False):
    """
    Shared state for the supervisor agent workflow.
    This state is passed between all agents and persisted via checkpointer.
    """
    # Session identification
    session_id: int
    file_path: str
    
    # Document extraction results
    pages: List[str]
    tables: List[Any]
    table_count: int
    
    # Analysis results
    analysis_result: Optional[str]
    compliance_result: Optional[str]
    risk_result: Optional[str]
    report_path: Optional[str]
    
    # RAG Interactive
    user_query: Optional[str]
    rag_response: Optional[str]
    
    # Workflow control
    current_agent: str
    next_agent: str
    status: Literal["pending", "processing", "awaiting_approval", "completed", "failed"]
    
    # Message history for progress tracking
    messages: List[dict]
    
    # Human-in-the-loop
    requires_human_approval: bool
    human_feedback: Optional[str]
    approval_checkpoint: Optional[str]
    
    # Error handling and retry
    error: Optional[str]
    retry_count: int
    max_retries: int
    last_error_agent: Optional[str]
    
    # Timestamps
    created_at: str
    updated_at: str


def create_initial_state(session_id: int, file_path: str, user_query: Optional[str] = None) -> AgentState:
    """Create initial state for a new workflow run."""
    now = datetime.utcnow().isoformat()
    return AgentState(
        session_id=session_id,
        file_path=file_path,
        user_query=user_query,
        rag_response=None,
        pages=[],
        tables=[],
        table_count=0,
        analysis_result=None,
        compliance_result=None,
        risk_result=None,
        report_path=None,
        current_agent="supervisor",
        next_agent="document_extraction",
        status="pending",
        messages=[],
        requires_human_approval=False,
        human_feedback=None,
        approval_checkpoint=None,
        error=None,
        retry_count=0,
        max_retries=3,
        last_error_agent=None,
        created_at=now,
        updated_at=now,
    )


def add_message(state: AgentState, agent: str, message: str) -> AgentState:
    """Add a progress message to the state."""
    state["messages"].append({
        "agent": agent,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    })
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def set_error(state: AgentState, agent: str, error: str) -> AgentState:
    """Set error state for an agent."""
    state["error"] = error
    state["last_error_agent"] = agent
    state["status"] = "failed"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def clear_error(state: AgentState) -> AgentState:
    """Clear error state for retry."""
    state["error"] = None
    state["status"] = "processing"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def request_human_approval(state: AgentState, checkpoint: str) -> AgentState:
    """Set state to require human approval at a checkpoint."""
    state["requires_human_approval"] = True
    state["approval_checkpoint"] = checkpoint
    state["status"] = "awaiting_approval"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def provide_human_feedback(state: AgentState, feedback: str) -> AgentState:
    """Record human feedback and clear approval requirement."""
    state["human_feedback"] = feedback
    state["requires_human_approval"] = False
    state["approval_checkpoint"] = None
    state["status"] = "processing"
    state["updated_at"] = datetime.utcnow().isoformat()
    return state
