"""Analysis Agent — Phase 5.

Retrieves the most relevant chunks from ChromaDB (after local and/or external
papers have been stored) and calls Claude to generate a structured literature
review: summary, agreements, contradictions, research gaps, and citations.
"""

import json

from anthropic import AsyncAnthropic

from app.config import settings
from app.tools import vector_store

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

Return a JSON object with exactly these keys:
{
  "summary": "<2–4 sentence overview of the state of research on the topic>",
  "agreements": ["<consensus finding [ref]>", ...],
  "contradictions": ["<conflicting findings [refs]>", ...],
  "researchGaps": ["<identified gap or open question>", ...],
  "citations": [
    {
      "index": 1,
      "title": "<exact title from Papers list>",
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
    """Retrieve relevant chunks and generate a literature review with Claude.

    Always re-queries ChromaDB after process_agent has stored any external
    papers, so both local and external content are considered.

    Populates:
        state["analysis"] – dict with summary, agreements, contradictions,
                            researchGaps, citations
    """
    question: str = state["question"]

    # Re-query now that all papers (local + external) are in ChromaDB
    n_fetch = max(settings.min_relevant_chunks * 3, 30)
    chunks = await vector_store.query(question, n_results=n_fetch)

    if not chunks:
        # No content at all — return a graceful empty analysis
        return {
            **state,
            "analysis": {
                "summary": "No relevant papers found for this query.",
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

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if Claude wraps in ```json ... ```
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
        # If Claude returns non-JSON, wrap the raw response as a summary
        analysis = {
            "summary": raw_text[:2000],
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
