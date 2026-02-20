"""Retry logic with exponential backoff for connection operations."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

__all__ = ["retry_with_backoff"]

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    max_retries: int,
    initial_backoff: float,
    backoff_multiplier: float,
    max_backoff: float,
) -> T:
    """Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff delay in seconds
        backoff_multiplier: Multiplier for exponential backoff
        max_backoff: Maximum backoff delay in seconds

    Returns:
        Result of the function call

    Raises:
        Exception: The last exception raised if all retries fail
    """
    backoff = initial_backoff
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt == max_retries - 1:
                # Last attempt failed, re-raise
                raise

            # Wait before retrying
            await asyncio.sleep(backoff)

            # Exponential backoff with max limit
            backoff = min(backoff * backoff_multiplier, max_backoff)

    # Should never reach here, but for type safety
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry state")
