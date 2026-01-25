# backend/workflows/supervisor.py
"""
Supervisor Agent for orchestrating the financial analysis workflow.
Routes between worker agents based on current state and handles coordination.
"""

import logging
from typing import Literal
from .state import AgentState, add_message

logger = logging.getLogger(__name__)

# Define agent routing order and dependencies
AGENT_ORDER = [
    "document_extraction",
    "extraction_review",  # Human checkpoint
    "parallel_analysis",  # finance_analysis + compliance run in parallel
    "risk_assessment",
    "report_generation",
    "report_approval",    # Human checkpoint
]

# Agents that require human approval before proceeding
HUMAN_CHECKPOINTS = ["extraction_review", "report_approval"]

# Agents that can run in parallel
PARALLEL_AGENTS = {
    "parallel_analysis": ["finance_analysis", "compliance"]
}


class SupervisorAgent:
    """
    Supervisor agent that coordinates the workflow by routing between agents.
    Implements hierarchical control over worker agents.
    """
    
    def __init__(self):
        self.agent_order = AGENT_ORDER
        self.human_checkpoints = HUMAN_CHECKPOINTS
        self.parallel_agents = PARALLEL_AGENTS
    
    def route_next_agent(self, state: AgentState) -> str:
        """
        Determine the next agent to run based on current state.
        
        Args:
            state: Current workflow state
            
        Returns:
            Name of the next agent to execute
        """
        current = state.get("current_agent", "supervisor")
        status = state.get("status", "pending")
        
        # If there's an error, don't proceed
        if status == "failed":
            logger.info(f"Workflow failed at {current}, not routing further")
            return "end"
        
        # If awaiting human approval, stay at current checkpoint
        if status == "awaiting_approval":
            logger.info(f"Awaiting human approval at {state.get('approval_checkpoint')}")
            return "wait_for_approval"
        
        # Find next agent in sequence
        try:
            current_idx = self.agent_order.index(current)
            if current_idx < len(self.agent_order) - 1:
                next_agent = self.agent_order[current_idx + 1]
                logger.info(f"Routing from {current} to {next_agent}")
                return next_agent
            else:
                logger.info(f"Workflow complete after {current}")
                return "end"
        except ValueError:
            # Current agent not in order, start from beginning or based on state
            return self._infer_next_agent(state)
    
    def _infer_next_agent(self, state: AgentState) -> str:
        """Infer next agent based on what's completed in state."""
        if state.get("report_path"):
            return "report_approval"
        elif state.get("risk_result"):
            return "report_generation"
        elif state.get("analysis_result") and state.get("compliance_result"):
            return "risk_assessment"
        elif state.get("pages") and state.get("human_feedback"):
            return "parallel_analysis"
        elif state.get("pages"):
            return "extraction_review"
        else:
            return "document_extraction"
    
    def should_continue(self, state: AgentState) -> bool:
        """
        Determine if the workflow should continue execution.
        
        Args:
            state: Current workflow state
            
        Returns:
            True if workflow should continue, False otherwise
        """
        status = state.get("status", "pending")
        
        if status in ["completed", "failed"]:
            return False
        
        if status == "awaiting_approval":
            return False  # Must wait for human input
        
        return True
    
    def is_human_checkpoint(self, agent: str) -> bool:
        """Check if the given agent is a human-in-the-loop checkpoint."""
        return agent in self.human_checkpoints
    
    def get_parallel_agents(self, agent: str) -> list[str] | None:
        """Get list of agents to run in parallel, if applicable."""
        return self.parallel_agents.get(agent)
    
    def handle_error(self, state: AgentState, agent: str, error: str) -> AgentState:
        """
        Handle an error from an agent.
        
        Args:
            state: Current workflow state
            agent: Agent that encountered the error
            error: Error message
            
        Returns:
            Updated state with error information
        """
        logger.error(f"Agent {agent} encountered error: {error}")
        
        state["error"] = error
        state["last_error_agent"] = agent
        state["status"] = "failed"
        state = add_message(state, "supervisor", f"Error in {agent}: {error}")
        
        return state
    
    def resume_after_approval(self, state: AgentState, feedback: str = None) -> AgentState:
        """
        Resume workflow after human approval.
        
        Args:
            state: Current workflow state
            feedback: Optional feedback from human
            
        Returns:
            Updated state ready to continue
        """
        checkpoint = state.get("approval_checkpoint")
        
        state["requires_human_approval"] = False
        state["approval_checkpoint"] = None
        state["status"] = "processing"
        
        if feedback:
            state["human_feedback"] = feedback
            state = add_message(state, "human", f"Feedback: {feedback}")
        
        state = add_message(state, "supervisor", f"Approved at {checkpoint}, resuming workflow")
        
        # Move to next agent after the checkpoint
        state["current_agent"] = checkpoint
        
        return state


def supervisor_node(state: AgentState) -> AgentState:
    """
    LangGraph node function for the supervisor.
    Updates state with routing decision.
    """
    supervisor = SupervisorAgent()
    
    next_agent = supervisor.route_next_agent(state)
    state["next_agent"] = next_agent
    state["current_agent"] = "supervisor"
    state = add_message(state, "supervisor", f"Routing to: {next_agent}")
    
    return state


def route_after_supervisor(state: AgentState) -> str:
    """
    Conditional edge function for LangGraph.
    Returns the name of the next node based on supervisor's routing decision.
    """
    return state.get("next_agent", "end")
