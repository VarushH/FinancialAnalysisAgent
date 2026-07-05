# backend/workflows/retry.py
"""
Retry utilities for agent execution.
Provides decorators for handling TRANSIENT failures within a live run.

Recovery from TERMINAL failures (process crash / restart) is not handled here:
it is provided natively by the durable LangGraph checkpointer. Resuming a
failed session via resume_analysis_pipeline() -> ainvoke(None, config)
continues from the last checkpoint. See financial_analysis_workflow.py.
"""

import asyncio
import functools
import logging
from typing import Callable, TypeVar, Any
from .state import AgentState, set_error, clear_error, add_message

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def agent_retry(agent_name: str):
    """
    Decorator specifically for agent functions that work with AgentState.
    Handles state updates for retries and errors.
    
    Args:
        agent_name: Name of the agent for logging and state updates
    """
    def decorator(func: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
        @functools.wraps(func)
        async def wrapper(state: AgentState) -> AgentState:
            max_retries = state.get("max_retries", 3)
            
            for attempt in range(max_retries + 1):
                try:
                    # Clear any previous error before retry
                    if attempt > 0:
                        state = clear_error(state)
                        state = add_message(
                            state, 
                            agent_name, 
                            f"Retrying (attempt {attempt + 1}/{max_retries + 1})..."
                        )
                    
                    result = await func(state)
                    return result
                    
                except Exception as e:
                    state["retry_count"] = attempt + 1
                    
                    if attempt < max_retries:
                        delay = min(1.0 * (2.0 ** attempt), 30.0)
                        logger.warning(
                            f"Agent {agent_name} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        state = add_message(
                            state,
                            agent_name,
                            f"Error occurred, will retry: {str(e)[:100]}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Agent {agent_name} failed after {max_retries + 1} attempts: {e}")
                        state = set_error(state, agent_name, str(e))
                        return state
            
            return state
        
        return wrapper
    return decorator


