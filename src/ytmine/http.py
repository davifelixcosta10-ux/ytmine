"""The canonical httpx2 client factory. Every production default is on.

The response hook logs at DEBUG, which is off unless the caller turns the
``ytmine.http`` logger on — the CLI stays quiet, and a bad API response can
still be traced.
"""

from __future__ import annotations

import logging
import socket
from typing import Final

import httpx2

logger = logging.getLogger(__name__)

_LIMITS: Final = httpx2.Limits(
    max_connections=200,
    max_keepalive_connections=40,
    keepalive_expiry=30.0,
)

_TIMEOUT: Final = httpx2.Timeout(
    connect=5.0,
    read=30.0,
    write=10.0,
    pool=10.0,
)

_SOCKET_OPTIONS: Final = ((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),)


def _log_response(response: httpx2.Response) -> None:
    """Log one line per response: method, url, status, HTTP version."""
    logger.debug(
        "http %s %s -> %d (%s)",
        response.request.method,
        response.request.url,
        response.status_code,
        response.http_version,
    )


def create_async_client() -> httpx2.AsyncClient:
    """Build the canonical async client: HTTP/2, brotli+zstd, retries, TCP_NODELAY."""
    transport = httpx2.AsyncHTTPTransport(
        http2=True,
        retries=3,
        limits=_LIMITS,
        socket_options=list(_SOCKET_OPTIONS),
    )
    return httpx2.AsyncClient(
        transport=transport,
        timeout=_TIMEOUT,
        follow_redirects=True,
        event_hooks={"response": [_log_response]},
    )
