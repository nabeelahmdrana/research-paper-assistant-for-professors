"""Shared AsyncOpenAI client singleton.

All agents (query_processor, query_expander, analysis_agent) import
``get_openai_client()`` instead of constructing their own AsyncOpenAI
instances.  A single shared client reuses the underlying httpx connection
pool, enabling HTTP/2 keep-alive to api.openai.com and eliminating the
repeated TLS handshake cost that occurs when each agent creates its own client.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Return the module-level AsyncOpenAI singleton, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _client
