# backend/workflows/checkpointer.py
"""
Checkpointer configuration for state persistence.
Uses MemorySaver for reliable in-process state persistence.
"""

import os
from pathlib import Path
from langgraph.checkpoint.memory import MemorySaver

# Global checkpointer instance for state persistence across workflow runs
_checkpointer = None

# Simple state cache for preview access (session_id -> state)
_state_cache = {}


def get_checkpointer() -> MemorySaver:
    """
    Get or create the checkpointer for workflow state persistence.
    Uses MemorySaver for reliable operation.
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
    return _checkpointer


def get_checkpoint_config(session_id: int, checkpoint_id: str = None) -> dict:
    """Create checkpoint configuration for a workflow run."""
    config = {
        "configurable": {
            "thread_id": f"session_{session_id}",
        }
    }
    
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id
        
    return config


def save_state_for_preview(session_id, state: dict):
    """Save state to cache for preview access."""
    global _state_cache
    # Ensure session_id is always int for consistent cache keys
    cache_key = int(session_id) if session_id is not None else None
    if cache_key is not None:
        _state_cache[cache_key] = state.copy()
        print(f"   📦 State cached for session {cache_key}")
        print(f"   📦 Cached report_path: {state.get('report_path')}")
        print(f"   📦 All cached session IDs: {list(_state_cache.keys())}")


def get_cached_state(session_id) -> dict | None:
    """Get cached state for preview."""
    # Ensure session_id is always int for consistent cache keys
    cache_key = int(session_id) if session_id is not None else None
    print(f"   📦 Looking for session {cache_key}")
    print(f"   📦 Available cache keys: {list(_state_cache.keys())}")
    return _state_cache.get(cache_key)


def clear_cached_state(session_id: int):
    """Clear cached state for a session."""
    global _state_cache
    if session_id in _state_cache:
        del _state_cache[session_id]


def clear_checkpointer():
    """Clear the global checkpointer (useful for testing)."""
    global _checkpointer, _state_cache
    _checkpointer = None
    _state_cache = {}
