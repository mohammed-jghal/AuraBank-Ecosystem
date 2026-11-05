# ADR-002 — RAG store: local in-memory TF-IDF, not Pinecone

Status: Accepted (PoC 0.1.0) · Date: 2026-11-05

## Context

Agents must ground decisions in policy documents (loan, fraud, KYC).
The document specifies Pinecone as the vector DB.

## Decision

Use a local TF-IDF retriever (`src/rag.py`, stdlib only) over the 3
policy files in `data/policies/`. Cost $0, latency ~1 ms, deterministic,
no network, no account.

## Alternatives considered

| Alternative | Cost | Latency | Why rejected for the PoC |
|---|---:|---:|---|
| Pinecone (managed) | ~$70+/month starter, plus embedding API costs | 20-100 ms + network | 3 short documents do not need a managed vector DB; adds a vendor, a key, and a failure mode for zero retrieval gain |
| ChromaDB (local) | $0, one dependency | ~5-20 ms | Reasonable, but adds an embedding model + dependency for 3 docs; TF-IDF already retrieves the right chunk in tests |
| Postgres pgvector | $0 if Postgres exists | ~5-20 ms | Justified when policy docs live alongside transactional data; no Postgres in this PoC |
| No RAG (rules hard-coded) | $0 | 0 ms | Rejected: policy changes would require code changes; RAG keeps policy editable by non-engineers |

## Consequences

- Positive: retrieval is tested (4 RAG tests), a miss returns empty so
  the orchestrator falls back to defaults instead of hallucinating.
- Negative: TF-IDF has no semantics — synonyms and paraphrases miss.
  Acceptable for 3 short policies with controlled vocabulary.
- Reversal condition: switch to ChromaDB/Pinecone when policy docs
  exceed ~100 documents, or when retrieval recall on a labelled
  policy-QA set falls below 80% (measure it before switching).
