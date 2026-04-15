"""Query Expander Agent — Sprint 4.

Generates 3 rephrasings of the original research question using gpt-4o-mini.
The sub-queries are stored in state["sub_queries"] so the retriever can run
parallel searches for all variants and merge results via RRF before selecting
the top candidates.

Reads:
    state["question"]   — the original research question

Populates:
    state["sub_queries"]  — list of 3 rephrased question strings, or [] on failure
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.tools.openai_client import get_openai_client

logger = logging.getLogger(__name__)

_EXPANSION_PROMPT = (
    "Generate exactly 3 rephrasings of the following research question. "
    "Return only a JSON array of 3 strings, no other text.\n"
    "Question: {question}"
)


async def query_expander(state: dict) -> dict:
    """Expand the original question into 3 paraphrased sub-queries.

    On any failure (network error, invalid JSON, etc.) the agent sets
    sub_queries to an empty list and the pipeline proceeds using only
    the original question.

    Args:
        state: Pipeline state dict; must contain ``question``.

    Returns:
        Updated state with ``sub_queries`` populated.
    """
    question: str = state.get("question", "")

    if not question:
        return {**state, "sub_queries": []}

    client = get_openai_client()

    sub_queries: list[str] = []
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=256,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": _EXPANSION_PROMPT.format(question=question),
                }
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            sub_queries = [str(q) for q in parsed if q][:3]
        logger.info(
            "QueryExpander: generated %d sub-queries for question '%s…'",
            len(sub_queries),
            question[:60],
        )
    except Exception as exc:
        logger.warning(
            "QueryExpander: failed to generate sub-queries (%s) — proceeding with original query",
            exc,
        )
        sub_queries = []

    return {**state, "sub_queries": sub_queries}
