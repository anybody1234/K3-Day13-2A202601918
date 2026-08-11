from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from .pii import scrub_text

SAFE_CORRELATION_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def new_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


def may_echo(incoming: str) -> bool:
    # The correlation id is a join key, so the log scrubber leaves it alone. That makes
    # this the only place a caller-supplied id can be rejected: a header like
    # `x-request-id: 0987654321` would otherwise reach the logs verbatim.
    return bool(SAFE_CORRELATION_ID.fullmatch(incoming)) and scrub_text(incoming) == incoming


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Worker tasks are reused between requests; clear first so metadata cannot leak.
        clear_contextvars()

        # Reuse the caller's id so a trace can span services, but only when it is safe
        # to echo back into logs and response headers.
        incoming = request.headers.get("x-request-id", "")
        correlation_id = incoming if may_echo(incoming) else new_correlation_id()

        # Bind before call_next: the downstream app runs in a task spawned from here and
        # only inherits a copy of the context taken at spawn time.
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.1f}"

        return response
