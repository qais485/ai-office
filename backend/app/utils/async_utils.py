"""Utility to run async coroutines from sync code safely."""
import asyncio
import concurrent.futures
from typing import Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine) -> T:
    """Run an async coroutine from sync code, handling nested event loops.

    Uses a new event loop in a separate thread when called from within
    an already-running loop (e.g. FastAPI sync dependencies, APScheduler).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            def _run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_run_in_new_loop).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
