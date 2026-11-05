# ADR-004 — Security model: blocklist guardrail, not an LLM firewall

Status: Accepted (PoC 0.1.0) · Date: 2026-11-05

## Context

The document claims the system "prevents prompt injection" with a
100% block rate via an LLM firewall (Lakera). No test evidence exists.

## Decision

Ship a deterministic blocklist guardrail (`src/guardrails.py`) as the
ONLY injection defence in this PoC, and report its measured block rate
honestly: 10/10 on a fixed malicious set, 0/3 benign blocked
(docs/MEASUREMENTS.md). Do NOT claim 100%.

## Alternatives considered

| Alternative | Cost | Why not in the PoC |
|---|---|---|
| Lakera / LLM firewall (managed) | Paid API, per-request latency + cost | Correct for production; needs an account, a key, and network. Cannot be tested offline, so it cannot be measured here |
| LLM-as-judge for injection | Token cost per request, non-deterministic | The judge can itself be injected; adds latency and a second failure mode |
| Output validation only | $0 | Necessary but insufficient: it catches bad outputs, not bad inputs reaching the agent |
| No guardrail (prompt engineering only) | $0 | Rejected explicitly: the document's own Finding 3 calls this a critical enterprise risk |

## Threat model (what the blocklist does and does not do)

- Blocks: known phrase patterns in free-text notes (the 19 phrases in
  `BLOCKED_PHRASES`, tested).
- Does NOT block: paraphrased injection, encoded payloads, multi-turn
  injection, indirect injection via a document, or injection in a
  language other than English.
- Defence in depth that IS present: input validation (amount/term
  bounds), HITL on high amounts and fraud flags, audit logging of
  every decision, no raw PII in logs, no secrets in the repo.
- Defence in depth that is NOT present and is required before any
  real deployment: managed LLM firewall, output schema validation,
  rate limiting, authentication, TLS, PII encryption at rest (AES-256
  is claimed in the document but not implemented here — the PoC stores
  no real PII at all), and red-team testing. See docs/FAILURE_MODES.md.
