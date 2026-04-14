# Research Paper Assistant — System Design & Implementation Spec

## Overview

This system is an AI-powered research assistant for professors. It enables users to:

- Ask research questions
- Retrieve answers from local and external academic sources
- Generate structured literature reviews
- Avoid hallucinations by grounding responses in real papers
- Improve over time using caching and learned knowledge

---

## Core Principles

1. Never fabricate sources
2. Prefer local knowledge over external
3. Minimize token usage
4. Maximize reuse via caching
5. Allow user control for external ingestion
6. Use hybrid retrieval (semantic + keyword)
7. Store only high-quality, relevant data

---

## System Architecture

### High-Level Flow
User Query
↓
Query Processing Layer
↓
Answer Cache Check
↓
Retrieval Cache Check
↓
Local Retrieval (Hybrid Search)
↓
Reranking
↓
Confidence Scoring
↓
IF High Confidence → Generate Answer
ELSE → External Search Flow


---

## Components

### 1. Query Processing Layer

#### Responsibilities:
- Query rewriting
- Query expansion
- Embedding generation

#### Example:
Input:"AI in diagnosis"
Output:
["machine learning medical diagnosis",
"AI clinical decision systems",
"limitations of AI in healthcare"]


---

### 2. Caching Layer (CRITICAL)

#### A. Answer Cache
- Key: Query embedding
- Value: Final structured answer

#### B. Retrieval Cache
- Key: Query embedding
- Value: Top retrieved chunks / papers

#### Matching:
- Use cosine similarity threshold (e.g. > 0.9)

---

### 3. Local Database (ChromaDB)

#### Collections:

##### `papers`
- id
- title
- authors
- abstract
- year
- source
- embedding

##### `chunks`
- id
- paper_id
- text
- section
- embedding

##### `answers`
- id
- query
- answer
- embedding
- sources_used

---

### 4. Chunking Strategy

- Chunk size: 300–800 tokens
- Overlap: 50–100 tokens
- Preserve:
  - section headings
  - citations

---

### 5. Retrieval Layer

#### Hybrid Search:

1. Vector Search (primary)
2. Keyword Search (BM25)
3. Metadata filtering

#### Output:
Top 30 chunks

---

### 6. Reranking Layer

- Input: Top 30 chunks
- Output: Top 8–12 chunks

Use:
- Cross-encoder OR reranker model

---

### 7. Confidence Scoring

Compute based on:
- Average similarity score
- Number of distinct sources
- Agreement across sources

#### Threshold:
confidence >= 0.7 → proceed locally
confidence < 0.7 → external search


---

## Local Answer Flow
Chunks → Compression → LLM → Structured Output


### Output Format:

- Summary
- Agreements
- Contradictions
- Research Gaps
- Citations

---

## External Search Flow (MCP Servers)

### Trigger Conditions:
- User selects "external"
- OR confidence < threshold

### Steps:

1. Query MCP servers:
   - arXiv
   - PubMed
   - bioRxiv
   - medRxiv

2. Fetch top 10–15 papers

3. Filter:
   - Must have abstract
   - Relevance score threshold

---

## External UX Flow

Instead of auto-answer:

### Show user:
- Top 3–5 papers
- Each includes:
  - Title
  - Abstract summary
  - Relevance score

### User actions:
- View summary
- Select papers
- Save to library

---

## Controlled Ingestion

When user saves a paper:

### Do NOT store full paper blindly

Store:
- High-value sections only
- Chunk + embed

### Metadata:
- Source
- Year
- Domain

---

## Final Answer Generation
Selected Papers + Local Chunks → LLM


Generate structured literature review.

---

## Storage After Answer

Save:

### 1. Answer Cache
- Query → Answer

### 2. Retrieval Cache
- Query → Relevant chunks/papers

### 3. Answer Embedding
- For future semantic matching

---

## Optimization Strategies

### 1. Token Reduction
- Use reranking
- Use chunk compression
- Limit context to top 8–12 chunks

### 2. Speed
- Cache-first approach
- Parallel retrieval (local + external)
- Cancel external if local sufficient

### 3. Storage Control
- Do not store all external papers
- Keep only high-quality, relevant ones

---

## API Design (FastAPI)

### POST `/query`
Input:
{
"query": "...",
"mode": "local | external | auto"
}


Output:
{
"answer": "...",
"sources": [],
"confidence": 0.85
}


---

### POST `/external-search`
Input:

{
"query": "..."
}


Output:

{
"papers": [
{
"title": "...",
"summary": "...",
"score": 0.92
}
]
}


---

### POST `/save-paper`
Input:

{
"paper_id": "...",
"content": "..."
}


---

### GET `/library`
Returns stored papers

---

## LangGraph Agent Design

### Nodes:

1. Query Processor
2. Cache Checker
3. Local Retriever
4. Reranker
5. Confidence Evaluator
6. External Search Agent
7. Answer Generator
8. Storage Agent

---

## Modes

### 1. Quick Mode
- Uses cache
- Minimal tokens
- Fast response

### 2. Deep Research Mode
- Full pipeline
- External search
- Contradiction detection

---

## Future Enhancements

- Knowledge graph (paper relationships)
- Claim-level contradiction detection
- Multi-user shared intelligence
- Citation network analysis

---

## Key Rules

- Never hallucinate sources
- Always ground answers in retrieved content
- Prefer reuse over recomputation
- Avoid storing low-quality data
- Keep system scalable and efficient

---

## Summary

This system evolves from a basic RAG pipeline into a:

- Cache-optimized
- Hybrid retrieval
- User-in-the-loop
- Multi-agent research system

Designed for:
- Accuracy
- Speed
- Scalability
