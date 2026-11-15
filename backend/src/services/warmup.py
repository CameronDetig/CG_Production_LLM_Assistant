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
import queue
import threading
import time
from typing import Callable, Dict, Iterator, Optional, Set, Union

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_warm = False
# Set by the streamed warmup once the assistant's code is loaded; the database is checked
# every time.
_assistant_warm = False
# The background load of the text embedding model, started once per container.
_search_model_thread: Optional[threading.Thread] = None

DATABASE_STEP = "database_pools"
# Only similarity searches need this, so the streamed warmup does not make requests wait for it.
SEARCH_MODEL_STEP = "text_embeddings"


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


def _ensure_database_awake() -> None:
    from src.services import database

    database.ensure_awake()


def _warm_database() -> str:
    """Open the pools if needed, then wait for the database to answer.

    Unlike the model steps this runs on every call: the database pauses on its own while the
    container stays warm, so a warm container says nothing about whether it is awake.
    """
    started = time.perf_counter()
    open_pools = _STEPS.get(DATABASE_STEP)
    if open_pools:
        open_pools()
    _ensure_database_awake()
    return f"{(time.perf_counter() - started) * 1000:.0f}ms"


def _warm_assistant() -> str:
    """Load the code every chat request needs, once per container."""
    global _assistant_warm
    started = time.perf_counter()
    with _lock:
        if _warm or _assistant_warm:
            return "warm"
        for name, step in _STEPS.items():
            if name not in (DATABASE_STEP, SEARCH_MODEL_STEP):
                step()
        _assistant_warm = True
    return f"{(time.perf_counter() - started) * 1000:.0f}ms"


def _start_search_model() -> str:
    """Begin loading the text embedding model without making anything wait for it.

    Most questions are answered with plain SQL and never use it. A similarity search that
    arrives before the load finishes waits for it inside get_text_embedding_model. Lambda
    pauses this thread between requests and resumes it during the next one.
    """
    global _search_model_thread
    step = _STEPS.get(SEARCH_MODEL_STEP)
    if _warm or step is None:
        return "warm"
    if _search_model_thread is not None:
        return "loading" if _search_model_thread.is_alive() else "warm"

    def load() -> None:
        global _search_model_thread
        try:
            step()
        except Exception:
            logger.exception("Background load of the search model failed")
            # Let the next warmup try again; a request that needs it loads it on demand.
            _search_model_thread = None

    _search_model_thread = threading.Thread(target=load, daemon=True)
    _search_model_thread.start()
    return "loading"


_GROUPS: Dict[str, Callable[[], str]] = {"database": _warm_database, "assistant": _warm_assistant}


def _pending_message(pending: Set[str]) -> str:
    if pending == {"database", "assistant"}:
        return "Waking the database and loading the assistant"
    if pending == {"database"}:
        return "Waking the database"
    return "Loading the assistant"


def warm_up_events() -> Iterator[Dict[str, object]]:
    """Warm the container and the database, yielding a status event at each change.

    Events have the shape of the chat stream's `status` events ({"stage", "message"}) so
    clients show them the same way:

    - "server_ready": this container is running (a cold start is already over by now).
    - "warming": the message names what is still in progress.
    - "ready": a question can be answered now; "steps" holds how long each part took.
    - "partial": something failed. It is reported, never raised, and retried next call.

    The database resume is network wait while loading code is CPU work, so the two run side
    by side instead of one after the other. The text embedding model loads in the background
    and is not waited for: this request has to end before the container can take a question.
    """
    yield {"stage": "server_ready", "message": "Server is up"}
    search_model = _start_search_model()

    finished: "queue.Queue[tuple]" = queue.Queue()

    def run(group: str, work: Callable[[], str]) -> None:
        try:
            finished.put((group, work()))
        except Exception:
            logger.exception("Warmup of %s failed", group)
            finished.put((group, "failed"))

    for group, work in _GROUPS.items():
        threading.Thread(target=run, args=(group, work), daemon=True).start()

    pending = set(_GROUPS)
    results: Dict[str, str] = {}
    yield {"stage": "warming", "message": _pending_message(pending)}
    while pending:
        group, outcome = finished.get()
        pending.discard(group)
        results[group] = outcome
        if pending:
            yield {"stage": "warming", "message": _pending_message(pending)}

    if search_model == "loading" and _search_model_thread is not None and not _search_model_thread.is_alive():
        search_model = "warm"
    results["search_model"] = search_model
    logger.info("Streamed warmup finished: %s", results)
    if results["database"] == "failed":
        yield {"stage": "partial", "message": "The database is not responding yet", "steps": results}
    elif results["assistant"] == "failed":
        yield {"stage": "partial", "message": "The assistant is not fully loaded yet", "steps": results}
    else:
        yield {"stage": "ready", "message": "Ready", "steps": results}
