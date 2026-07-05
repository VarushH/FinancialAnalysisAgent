# backend/workflows/checkpointer.py
"""
Checkpointer configuration for state persistence.
Uses MemorySaver for reliable in-process state persistence.
"""

# import os
# from pathlib import Path
# from langgraph.checkpoint.memory import MemorySaver

# # Global checkpointer instance for state persistence across workflow runs
# _checkpointer = None

# # Simple state cache for preview access (session_id -> state)
# _state_cache = {}


# def get_checkpointer() -> MemorySaver:
#     """
#     Get or create the checkpointer for workflow state persistence.
#     Uses MemorySaver for reliable operation.
#     """
#     global _checkpointer
#     if _checkpointer is None:
#         _checkpointer = MemorySaver()
#     return _checkpointer

import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_DB_PATH = "langgraph_checkpoints.sqlite"

# The pipeline runs entirely through ainvoke/astream, so it needs an async
# checkpointer. The Django status endpoint reads state synchronously, so it
# gets its own sync checkpointer. Both point at the same WAL-mode sqlite
# file, which is what keeps the two connections from blocking each other.
_sync_checkpointer = None


@asynccontextmanager
async def async_checkpointer():
    """
    Fresh async checkpointer, scoped to a single pipeline run.

    AsyncSqliteSaver wraps an aiosqlite connection whose internal asyncio.Lock
    is bound to the event loop active when it's created. The pipeline is
    invoked via async_to_sync from sync Django views, and each such call can
    run on a new event loop - so a cached/global AsyncSqliteSaver breaks with
    "bound to a different event loop" the moment a later call lands on a
    different loop. Opening (and closing) a new connection per run avoids
    that entirely.
    """
    conn = await aiosqlite.connect(_DB_PATH)
    try:
        await conn.execute("PRAGMA journal_mode=WAL;")
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        yield saver
    finally:
        await conn.close()


def get_checkpointer() -> SqliteSaver:
    """
    Sync checkpointer for read-only state lookups (e.g. the status endpoint).
    WAL mode reduces lock contention between the pipeline thread and the
    status-endpoint thread.
    """
    global _sync_checkpointer
    if _sync_checkpointer is None:
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        _sync_checkpointer = SqliteSaver(conn)
        _sync_checkpointer.setup()
    return _sync_checkpointer




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



def clear_checkpointer():
    """Clear the global sync checkpointer (useful for testing)."""
    global _sync_checkpointer
    _sync_checkpointer = None
