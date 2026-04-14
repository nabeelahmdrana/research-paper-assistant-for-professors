# Research Paper Assistant — Production-Ready Scalable Architecture (Simplified, Non-Overengineered)## 1. OverviewThis system is an AI-powered research assistant for professors that:- Accepts research questions- Retrieves relevant academic literature from local and external sources- Generates structured literature reviews (summary, agreements, contradictions, gaps)- Continuously improves through caching and incremental learning- Ensures grounded responses with no hallucinated citations---## 2. Design PhilosophyThis architecture balances:- ✅ Production-grade scalability- ✅ High retrieval accuracy- ✅ Low operational complexity- ✅ Minimal LLM/token waste- ❌ No over-engineered agent graphs- ❌ No unnecessary multi-stage pipelines- ❌ No redundant caching layers---## 3. High-Level System Flow
User Query
↓
Query Embedding
↓
Answer Cache Check (semantic similarity)
↓
IF HIT → return cached answer
ELSE:
↓
Hybrid Retrieval (Vector + BM25)
↓
Rerank Top Results
↓
Confidence Scoring
↓
IF confidence ≥ threshold:
→ Generate Answer (LLM)
ELSE:
→ External Search (MCP)
→ Rerank External Papers
→ Generate Answer
↓
Store Answer + Sources
---## 4. Core Modules### 4.1 Query Processor (Lightweight)Responsibilities:- Normalize query text- Generate embedding- (Optional later) simple query rewriteOutput:```json{  "query": "...",  "embedding": [...],  "normalized_query": "..."}

4.2 Answer Cache (CRITICAL COMPONENT)
Purpose:


Avoid redundant LLM calls


Serve repeated or similar questions instantly


Storage:


ChromaDB collection: answers


Schema:


id


query


embedding


answer_json


source_ids


timestamp


Matching:


cosine similarity ≥ 0.93



4.3 Local Knowledge Base
Collections
1. papers


paper_id


title


authors


abstract


metadata (year, source)



2. chunks


chunk_id


paper_id


text


embedding


section (optional)



3. answers


cached query results


full structured responses



5. Ingestion Pipeline
5.1 Input Types


PDF upload


DOI fetch


URL ingestion



5.2 Processing Steps


Extract text


Clean noise


Chunk text:


Size: 500 tokens


Overlap: 50 tokens




Generate embeddings


Store:


Paper → papers


Chunks → chunks





5.3 Key Rule

External papers are NEVER stored blindly

Only:


relevant chunks


validated papers



6. Retrieval System
6.1 Hybrid Search
Two parallel systems:
Vector Search


Semantic similarity


ChromaDB


BM25 Search


Keyword matching


rank_bm25 (in-memory index)



6.2 Merge Strategy
Use:


Reciprocal Rank Fusion (RRF)


Output:


Top 30 unified chunks



7. Reranking Layer (Quality Filter)
Purpose:
Improve precision before LLM input
Process:


Input: Top 30 chunks


Output: Top 10–12 chunks


Model:


cross-encoder/ms-marco-MiniLM-L-6-v2



8. Confidence Scoring System
Purpose:
Decide:


Local answer OR external search


Inputs:


Average similarity score


Number of unique papers


Cross-source agreement


Output:
0.0 → 1.0 confidence score
Threshold:


≥ 0.70 → local answer


< 0.70 → external search



9. External Search (MCP Layer)
Triggered when:


low confidence OR


user explicitly requests external


Sources:


arXiv


PubMed


bioRxiv


medRxiv



Flow:


Query MCP servers


Fetch top 10–15 papers


Filter irrelevant results


Convert to summaries


Present top 3–5 to user



10. External UX Flow
User sees:


Paper title


Abstract summary


Relevance score


User can:


Select papers


Save to library


Reject irrelevant results



11. Answer Generation Layer
Input:


Reranked chunks (local OR external)


Output format:


Summary


Agreements


Contradictions


Research gaps


Citations (strict grounding)



12. Storage Strategy
After each query:
Store:
1. Answer Cache


query embedding → answer JSON


2. Provenance


chunk IDs used


paper IDs used


3. Metadata


confidence score


mode (local/external)



13. Caching Strategy
13.1 Answer Cache (Primary)


Prevents full recomputation


13.2 No Retrieval Cache (Intentionally omitted)
Reason:


low ROI


adds complexity



14. Performance Optimizations
14.1 Token Optimization


reranking reduces context size


avoid full paper injection



14.2 Search Optimization


hybrid retrieval avoids blind vector search failures



14.3 Model Optimization


reranker loaded once at startup


embeddings cached



15. Failure Handling
15.1 Reranker failure
Fallback:


use vector + BM25 top 10 directly



15.2 BM25 empty index
Fallback:


vector search only



15.3 External MCP failure
Fallback:


return local best effort result



16. API Design
POST /query
Request:
{  "query": "...",  "mode": "auto | local | external"}
Response:
{  "answer": {...},  "confidence": 0.82,  "mode_used": "local",  "sources": [...]}

POST /ingest


PDF / DOI / URL ingestion



GET /library


List all stored papers



GET /cache/stats


cache hit rate


avg confidence


external usage ratio



17. System Architecture (Simplified LangGraph)
query_processor   ↓cache_checker   ↓retriever (vector + BM25)   ↓reranker   ↓confidence_evaluator   ↓┌───────────────┐│ local path     ││ external path   │└───────────────┘   ↓answer_generator   ↓storage_agent

18. What is INTENTIONALLY NOT INCLUDED
To avoid overengineering:


❌ Full query expansion system (future improvement)


❌ Retrieval cache layer


❌ Complex multi-agent graph (8+ nodes)


❌ Knowledge graph of papers


❌ Claim-level contradiction engine


❌ Chunk compression pipeline



19. Future Upgrades (Optional)
These can be added later without refactor:


Query expansion (light LLM call)


Retrieval cache


Paper citation graph


Multi-user shared intelligence


Semantic deduplication across queries



20. Key Success Metrics


Cache hit rate ≥ 30%


External search ratio ≤ 40%


Avg latency < 3s local queries


Token usage reduced via reranking ≥ 40%


Citation accuracy = 100% grounded



21. Final Summary
This system is a balanced RAG architecture combining:


Fast caching layer


Hybrid retrieval (vector + keyword)


Lightweight reranking


Confidence-driven decision making


Controlled external search via MCP


It avoids unnecessary complexity while remaining fully scalable for production use.