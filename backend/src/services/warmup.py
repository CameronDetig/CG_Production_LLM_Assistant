"""Pre-load the expensive parts of a chat request.

The first chat request on a fresh Lambda container otherwise pays for importing the agent
stack (langgraph, transformers), loading the text embedding model, and opening both
PostgreSQL pools.  The browser calls /api/warmup after sign-in so that cost is paid while
the user is still typing their first question.

The work runs inside the request on purpose: Lambda freezes the container once the
response is returned, so a background thread would not reliably finish.
"""

import importlib
import logging
import threading
import time
from typing import Callable, Dict, Union

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_warm = False


def _load_agent_stack() -> None:
    importlib.import_module("src.core.chat_agent")


def _load_text_embeddings() -> None:
    from src.services.embeddings import get_text_embedding_model

    get_text_embedding_model()


def _open_database_pools() -> None:
    from src.services import database

    database.init_db_connection()
    database.init_readonly_db_connection()


_STEPS: Dict[str, Callable[[], None]] = {
    "agent_stack": _load_agent_stack,
    "text_embeddings": _load_text_embeddings,
    "database_pools": _open_database_pools,
}


def warm_up() -> Dict[str, Union[str, Dict[str, object]]]:
    """Run each warmup step once per container; later calls return immediately.

    A failing step is logged and reported but never raised, so warmup can never break a
    session.  The container only counts as warm when every step succeeded, so a transient
    failure (for example a database blip) is retried on the next call.
    """
    global _warm
    if _warm:
        return {"status": "warm"}

    with _lock:
        if _warm:
            return {"status": "warm"}

        results: Dict[str, object] = {}
        for name, step in _STEPS.items():
            started = time.perf_counter()
            try:
                step()
                results[name] = f"{(time.perf_counter() - started) * 1000:.0f}ms"
            except Exception:
                logger.exception("Warmup step %s failed", name)
                results[name] = "failed"

        _warm = all(value != "failed" for value in results.values())
        logger.info("Warmup finished: %s", results)
        return {"status": "warm" if _warm else "partial", "steps": results}
