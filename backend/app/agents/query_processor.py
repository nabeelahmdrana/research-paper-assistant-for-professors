"""Query Processor Agent — Phase B / Sprint 4 (HyDE).

Normalises the incoming query, generates its embedding, and also produces a
HyDE (Hypothetical Document Embedding) by:
  1. Asking gpt-4o-mini to write a 3-sentence academic passage that would
     answer the question.
  2. Embedding that hypothetical document with the same model used for chunks.

Both embeddings are stored in state so the retriever can search with both
and merge the result sets before RRF.

Embedding is generated via the OpenAI Embeddings API using the model
configured in settings.embedding_model (default: text-embedding-3-small).
This matches the embedding function used by ChromaDB for document indexing,
ensuring that query and document vectors are in the same space.

Populates:
    state["normalized_query"]  — stripped and lowercased query text
    state["query_embedding"]   — float list (1536-dim for text-embedding-3-small)
    state["hyde_embedding"]    — float list from the hypothetical document, or []
"""

from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_HYDE_PROMPT = (
    "Write a 3-sentence academic passage from a research paper that would "
    "directly answer the following question. Be specific and use academic language.\n"
    "Question: {question}"
)


async def query_processor(state: dict) -> dict:
    """Normalise the query and compute query + HyDE embeddings via the OpenAI API.

    HyDE failure is non-fatal: if the LLM call or embedding fails, hyde_embedding
    is set to [] and the pipeline proceeds with only the original query embedding.

    Args:
        state: Pipeline state dict; must contain ``question`` key.

    Returns:
        Updated state with ``normalized_query``, ``query_embedding``, and
        ``hyde_embedding`` added.
    """
    question: str = state.get("question", "")

    # Normalise: strip whitespace and lowercase for cache / BM25 matching
    normalized_query: str = question.strip().lower()

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    async def _embed(text: str) -> list[float]:
        """Embed a single text string via the OpenAI API."""
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def _generate_hyde_doc() -> str:
        """Generate a hypothetical academic passage via gpt-4o-mini."""
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=200,
            temperature=0.5,
            messages=[
                {
                    "role": "user",
                    "content": _HYDE_PROMPT.format(question=question),
                }
            ],
        )
        return (response.choices[0].message.content or "").strip()

    async def _query_embedding_task() -> list[float]:
        try:
            emb = await _embed(normalized_query)
            logger.debug(
                "QueryProcessor: generated embedding (dim=%d) for query '%s…'",
                len(emb),
                normalized_query[:60],
            )
            return emb
        except Exception as exc:
            logger.error("QueryProcessor: query embedding failed — %s", exc)
            return []

    async def _hyde_embedding_task() -> list[float]:
        try:
            hyde_doc = await _generate_hyde_doc()
            if hyde_doc:
                emb = await _embed(hyde_doc)
                logger.debug(
                    "QueryProcessor: generated HyDE embedding (dim=%d)", len(emb)
                )
                return emb
        except Exception as exc:
            logger.warning("QueryProcessor: HyDE generation failed (non-fatal) — %s", exc)
        return []

    # Run query embedding and HyDE generation concurrently to cut latency
    embedding, hyde_embedding = await asyncio.gather(
        _query_embedding_task(),
        _hyde_embedding_task(),
    )

    return {
        **state,
        "normalized_query": normalized_query,
        "query_embedding": embedding,
        "hyde_embedding": hyde_embedding,
    }
