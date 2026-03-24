"""Celery application instance for the stock analyst agent.

Creates the single shared `celery` object that all tasks import and register
against. Configuration is read entirely from `config.py` settings — no
hardcoded broker URLs, serialisers, or queue names in this file.

Serialisation:
    All tasks use JSON for both task payload and result storage.  Binary
    serialisers (pickle) are explicitly excluded from `accept_content` to
    prevent arbitrary code execution via a malformed broker message.

Task routing:
    Every task under `stock_agent.worker.tasks.*` is routed to the `analysis`
    queue.  This isolates analysis work from any future administrative or
    maintenance tasks that may be added on a separate queue.

Async boundary:
    Celery does NOT support `async def` task bodies.  All tasks in tasks.py
    MUST be defined as `def` (synchronous) and delegate async pipeline work to
    a private `async def _async_*()` helper called via `asyncio.run()`.
"""

from celery import Celery

from stock_agent.config import settings

# Single shared Celery instance — imported by tasks.py and all callers.
celery = Celery(
    "stock_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# --- Serialisation ---------------------------------------------------------
# Force JSON throughout the pipeline.  Pickle is the Celery default and a
# known remote-code-execution vector if the broker is ever compromised.
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]

# --- Task routing ----------------------------------------------------------
# Route all analysis tasks to the dedicated `analysis` queue.  Workers are
# started with `--queues analysis` so they only pick up analysis work.
# Future admin/maintenance tasks can be routed to a separate queue without
# changing anything here.
celery.conf.task_routes = {
    "stock_agent.worker.tasks.*": {"queue": "analysis"},
}
