"""Analysis Agent — Phase 5 / Phase B.

Uses the reranked chunks already selected by the retriever + reranker pipeline
to call an OpenAI-compatible LLM and generate a structured literature review:
summary, agreements, contradictions, research gaps, and citations.

If ``reranked_chunks`` is populated in state it is used directly.
If empty, the agent falls back to ``retrieved_chunks[:12]``.
As a last resort it re-queries ChromaDB directly (backward-compatible path).
"""

import json
import logging
import re
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.tools import vector_store

logger = logging.getLogger(__name__)

# Matches the start of the "summary" value inside the streamed JSON, e.g.:
#   "summary": "   or   "summary" : "
_SUMMARY_KEY_RE = re.compile(r'"summary"\s*:\s*"')


def _find_string_end(text: str) -> int:
    """Return the index of the first unescaped closing quote in *text*.

    *text* must start immediately after the opening quote of a JSON string
    value (i.e. the opening quote itself has already been consumed).

    Returns -1 when no closing quote has been received yet (partial stream).
    """
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2  # skip the escaped character
        elif ch == '"':
            return i
        else:
            i += 1
    return -1

_SYSTEM_PROMPT = """\
You are an expert academic research assistant helping a professor analyse the
literature on a topic. You will be given a research question and a set of
relevant text excerpts from academic papers. Your job is to produce a
structured literature review.

IMPORTANT RULES:
1. Base all claims exclusively on the provided text excerpts.
2. Never fabricate or infer paper titles, authors, or years not in the excerpts.
3. Use citation indices like [1], [2] etc. that correspond to the "Papers" list.
4. Return ONLY valid JSON — no markdown, no prose outside the JSON object.
5. The "summary" field MUST be at least 200 words. Write a thorough, detailed overview.
6. CRITICAL — relevance check: Before writing, verify the excerpts directly address the
   research question. If NONE of the excerpts address the research question (e.g. the
   question asks about physics but ALL excerpts discuss unrelated biology/medicine), set
   "summary" to exactly:
   "The papers in your library do not contain information relevant to this query. Please
   upload papers on this topic or use the external search feature to discover relevant
   literature." and set agreements, contradictions, researchGaps, and citations to empty
   arrays []. Never describe unrelated content as if it answers the question.
7. CITATIONS — only include papers in the "citations" array that you ACTUALLY REFERENCED
   in your summary or other fields. Do NOT list papers that are off-topic and not mentioned
   in your analysis. If a paper discusses a completely different field than the question,
   omit it from citations entirely. The citations array must contain ONLY papers that
   genuinely contributed to the answer.

Return a JSON object with exactly these keys:
{
  "summary": "<comprehensive overview of the state of research on the topic — must be at least 200 words, covering key themes, major findings, methodological approaches, and the overall trajectory of the field>",
  "agreements": ["<consensus finding [ref]>", ...],
  "contradictions": ["<conflicting findings [refs]>", ...],
  "researchGaps": ["<identified gap or open question>", ...],
  "citations": [
    {
      "index": 1,
      "title": "<exact title from Papers list — ONLY papers you actually cited>",
      "authors": ["<author1>", ...],
      "year": <year as integer or 0 if unknown>,
      "source": "<local|external>",
      "doi": "<doi or empty string>",
      "url": "<url or empty string>"
    }
  ]
}
"""


def _build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """Build the LLM context string and the ordered citation list.

    Deduplicates by paper_id so each paper appears once in the citation list,
    even if multiple chunks were retrieved.

    Returns:
        context_text: Formatted string of excerpts with citation references.
        citations: Ordered list of unique paper metadata dicts.
    """
    # Group chunks by paper_id so all excerpts from the same paper appear
    # contiguously in the context, improving LLM coherence.
    chunks = sorted(chunks, key=lambda c: c.get("metadata", {}).get("paper_id", ""))

    seen_paper_ids: dict[str, int] = {}  # paper_id → 1-based index
    citations: list[dict] = []
    excerpt_lines: list[str] = []

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        paper_id = meta.get("paper_id", "")

        if paper_id not in seen_paper_ids:
            idx = len(citations) + 1
            seen_paper_ids[paper_id] = idx

            authors_raw = meta.get("authors", "")
            if isinstance(authors_raw, list):
                authors = authors_raw
            else:
                authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()]

            year_raw = meta.get("year", "")
            try:
                year = int(year_raw)
            except (ValueError, TypeError):
                year = 0

            citations.append(
                {
                    "index": idx,
                    "paper_id": paper_id,
                    "title": meta.get("title", ""),
                    "authors": authors,
                    "year": year,
                    "source": meta.get("source", "local"),
                    "doi": meta.get("doi", "") or "",
                    "url": meta.get("url", "") or "",
                }
            )
        else:
            idx = seen_paper_ids[paper_id]

        excerpt_lines.append(f"[{idx}] {chunk.get('text', '')}")

    papers_block_lines = []
    for c in citations:
        authors_str = ", ".join(c["authors"]) if c["authors"] else "Unknown"
        papers_block_lines.append(
            f"[{c['index']}] {c['title']} — {authors_str} ({c['year'] or 'n.d.'})"
            f" [{c['source']}]"
        )

    context_text = (
        "Papers:\n"
        + "\n".join(papers_block_lines)
        + "\n\nExcerpts:\n"
        + "\n\n".join(excerpt_lines)
    )
    return context_text, citations


async def analysis_agent(state: dict) -> dict:
    """Generate a literature review using an OpenAI-compatible LLM.

    Chunk selection priority:
        1. state["reranked_chunks"]  — relevance-filtered by cross-encoder
        2. state["external_papers"]  — abstracts from external search (when local had no relevant chunks)

    Populates:
        state["analysis"] – dict with summary, agreements, contradictions,
                            researchGaps, citations
    """
    question: str = state["question"]

    # Use reranked chunks (already filtered by _MIN_RERANK_SCORE in reranker_agent).
    # Do NOT fall back to raw retrieved_chunks — those bypassed the relevance filter
    # and would reintroduce off-topic content that the reranker deliberately excluded.
    chunks: list[dict] = state.get("reranked_chunks", [])

    if not chunks:
        # Reranked chunks empty means local library had nothing relevant.
        # Use external paper abstracts (populated by external_search_agent).
        external_papers: list[dict] = state.get("external_papers", [])
        for paper in external_papers[:10]:  # cap to avoid oversized context
            abstract = paper.get("abstract", "").strip()
            if abstract:
                chunks.append({
                    "text": abstract,
                    "metadata": {
                        "paper_id": paper.get("paper_id", ""),
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", []),
                        "year": paper.get("year", ""),
                        "source": "external",
                        "doi": paper.get("doi", ""),
                        "url": paper.get("url", ""),
                    },
                })
        if chunks:
            logger.info(
                "AnalysisAgent: using %d external paper abstracts as context",
                len(chunks),
            )

    # Cap total chunks to 15 to keep prompt + response within token limits
    chunks = chunks[:15]

    if not chunks:
        # No content at all — return a graceful empty analysis
        return {
            **state,
            "analysis": {
                "summary": "No relevant papers found for this query. Please upload papers to your library or try a different question.",
                "agreements": [],
                "contradictions": [],
                "researchGaps": [],
                "citations": [],
            },
        }

    context_text, citations = _build_context(chunks)

    user_message = (
        f"Research question: {question}\n\n"
        f"{context_text}\n\n"
        "Now produce the JSON literature review following the format in the system prompt."
    )

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    raw_text = ""
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=8192,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw_text = (response.choices[0].message.content or "").strip()

        # Strip markdown code fences in case the model still wraps output
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```", 2)[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        analysis = json.loads(raw_text)

        # Ensure citations carry full metadata (merge with our citation list)
        meta_by_index = {c["index"]: c for c in citations}
        merged_citations = []
        for cit in analysis.get("citations", []):
            idx = int(cit.get("index", 0))
            base = meta_by_index.get(idx, {})
            merged_citations.append(
                {
                    "index": idx,
                    "title": cit.get("title") or base.get("title", ""),
                    "authors": cit.get("authors") or base.get("authors", []),
                    "year": cit.get("year") or base.get("year", 0),
                    "source": cit.get("source") or base.get("source", "local"),
                    "doi": cit.get("doi") or base.get("doi", ""),
                    "url": cit.get("url") or base.get("url", ""),
                }
            )
        analysis["citations"] = merged_citations

    except json.JSONDecodeError:
        logger.error("AnalysisAgent: JSON decode failed on LLM response (len=%d)", len(raw_text))
        # Build citations from our own list since the LLM response wasn't parsed
        analysis = {
            "summary": raw_text[:500] if raw_text else "Analysis could not be generated.",
            "agreements": [],
            "contradictions": [],
            "researchGaps": [],
            "citations": [
                {
                    "index": c["index"],
                    "title": c["title"],
                    "authors": c["authors"],
                    "year": c["year"],
                    "source": c["source"],
                    "doi": c["doi"],
                    "url": c["url"],
                }
                for c in citations
            ],
        }

    return {
        **state,
        "analysis": analysis,
    }


async def stream_analysis(
    state: dict,
) -> AsyncGenerator[tuple[str, object], None]:
    """Streaming variant of analysis_agent.

    Yields:
        ("token", str)   — one text delta at a time as the LLM generates tokens.
        ("done", dict)   — the updated state dict with state["analysis"] populated,
                           emitted as the final item after the stream is exhausted
                           and the JSON response has been parsed.

    Intended to be consumed by the SSE streaming endpoint so individual tokens
    can be forwarded to the browser as they arrive.
    """
    question: str = state["question"]

    # Use reranked chunks (relevance-filtered). Do NOT fall back to raw
    # retrieved_chunks — they bypass the reranker's relevance filter.
    chunks: list[dict] = state.get("reranked_chunks", [])

    if not chunks:
        external_papers: list[dict] = state.get("external_papers", [])
        for paper in external_papers[:10]:
            abstract = paper.get("abstract", "").strip()
            if abstract:
                chunks.append({
                    "text": abstract,
                    "metadata": {
                        "paper_id": paper.get("paper_id", ""),
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", []),
                        "year": paper.get("year", ""),
                        "source": "external",
                        "doi": paper.get("doi", ""),
                        "url": paper.get("url", ""),
                    },
                })
        if chunks:
            logger.info(
                "StreamAnalysis: using %d external paper abstracts as context",
                len(chunks),
            )

    chunks = chunks[:15]

    if not chunks:
        empty_analysis = {
            "summary": "No relevant papers found for this query. Please upload papers to your library or try a different question.",
            "agreements": [],
            "contradictions": [],
            "researchGaps": [],
            "citations": [],
        }
        yield ("done", {**state, "analysis": empty_analysis})
        return

    context_text, citations = _build_context(chunks)

    user_message = (
        f"Research question: {question}\n\n"
        f"{context_text}\n\n"
        "Now produce the JSON literature review following the format in the system prompt."
    )

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    raw_text = ""
    # Tracks where inside raw_text the summary value begins (after opening ").
    # -1 means we haven't found the key yet.
    summary_value_start: int = -1
    # How many characters of raw_text we have already forwarded as tokens.
    summary_emitted_upto: int = 0
    # Set to True once the closing quote of the summary value is detected.
    summary_done: bool = False

    try:
        stream = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=8192,
            temperature=0.1,
            stream=True,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                raw_text += delta.content

                if summary_done:
                    # Summary already complete — just accumulate; don't emit
                    continue

                # Locate the start of the summary value if not yet found
                if summary_value_start == -1:
                    m = _SUMMARY_KEY_RE.search(raw_text)
                    if m:
                        summary_value_start = m.end()  # position after opening "
                        summary_emitted_upto = summary_value_start

                if summary_value_start == -1:
                    # Haven't reached the summary key yet
                    continue

                # Slice only the newly accumulated characters inside the value
                portion = raw_text[summary_emitted_upto:]
                if not portion:
                    continue

                end_idx = _find_string_end(portion)
                if end_idx >= 0:
                    # Closing quote found — emit up to (not including) the quote
                    if end_idx > 0:
                        yield ("token", portion[:end_idx])
                    summary_done = True
                else:
                    # Summary value still incomplete — forward what we have
                    yield ("token", portion)
                    summary_emitted_upto = len(raw_text)

    except Exception as exc:
        logger.error("StreamAnalysis: streaming error — %s", exc)
        yield ("done", {
            **state,
            "analysis": {
                "summary": f"Analysis failed: {exc}",
                "agreements": [],
                "contradictions": [],
                "researchGaps": [],
                "citations": [],
            },
        })
        return

    # Parse accumulated JSON and merge citation metadata
    try:
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```", 2)[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        analysis = json.loads(raw_text)

        meta_by_index = {c["index"]: c for c in citations}
        merged_citations = []
        for cit in analysis.get("citations", []):
            idx = int(cit.get("index", 0))
            base = meta_by_index.get(idx, {})
            merged_citations.append({
                "index": idx,
                "title": cit.get("title") or base.get("title", ""),
                "authors": cit.get("authors") or base.get("authors", []),
                "year": cit.get("year") or base.get("year", 0),
                "source": cit.get("source") or base.get("source", "local"),
                "doi": cit.get("doi") or base.get("doi", ""),
                "url": cit.get("url") or base.get("url", ""),
            })
        analysis["citations"] = merged_citations

    except json.JSONDecodeError:
        logger.error("StreamAnalysis: JSON decode failed (len=%d)", len(raw_text))
        analysis = {
            "summary": raw_text[:500] if raw_text else "Analysis could not be generated.",
            "agreements": [],
            "contradictions": [],
            "researchGaps": [],
            "citations": [
                {
                    "index": c["index"],
                    "title": c["title"],
                    "authors": c["authors"],
                    "year": c["year"],
                    "source": c["source"],
                    "doi": c["doi"],
                    "url": c["url"],
                }
                for c in citations
            ],
        }

    yield ("done", {**state, "analysis": analysis})
