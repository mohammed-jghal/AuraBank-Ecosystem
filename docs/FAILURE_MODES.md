# Failure Modes — AuraBank PoC

Each mode: trigger, what the user sees, fallback, blast radius, and
what would detect it in production. "Blast radius" is per single
request unless stated otherwise.

## 1. Hallucination under $10,000 (auto-approve path)

- Trigger: the scorer is deterministic rules, so true LLM hallucination
  cannot occur in this PoC — but a WRONG RULE can: e.g. a borderline
  score just above 650 with a thin file auto-approves a loan that a
  human would decline.
- What the user sees: an approval in milliseconds, no human involved.
- Fallback: low-confidence gate (< 0.60) forces HITL; the 550-649 band
  forces manual review. A score of 651 with confidence 0.95 still
  auto-approves — that is the residual risk.
- Blast radius: one loan, up to $10,000. Mitigation in production:
  cap auto-approval at a lower amount for thin files, and sample-audit
  5% of auto-approvals.
- Detection: audit-log sampling, and the false-positive count in
  MEASUREMENTS.md (currently 0/100 on synthetic data — do not trust
  that number in production).

## 2. CBS mock failure (customer not found / data missing)

- Trigger: `/loan/apply` with an unknown `customer_id`, or a customer
  record missing income fields.
- What the user sees: 404 unknown_customer, or a low-confidence
  decision (missing fields drop confidence by 0.08 each).
- Fallback: the API never crashes on missing data; the scorer treats
  missing fields as neutral (0.8 on-time ratio, 0.3 DTI) and lowers
  confidence, which pushes borderline cases to HITL.
- Blast radius: one request. In production the CBS is a single point
  of failure for the whole flow — the PoC has no CBS circuit breaker
  yet; add one before connecting a real CBS.

## 3. RAG miss (no policy chunk retrieved)

- Trigger: a query with no overlapping terms (e.g. a new product name).
- What the user sees: the decision proceeds on the default rules;
  `rag` in the response is an empty list.
- Fallback: defaults in code, not a hallucinated policy. The miss is
  visible in the response, not silent.
- Blast radius: one decision may apply a stale/default rule.
- Detection: log the retrieval score; alert when miss rate exceeds 5%.

## 4. LLM timeout / scorer failure

- Trigger: in this PoC the scorer is local and cannot time out. When
  an LLM scorer is plugged in, a timeout or 5xx is the expected
  failure.
- Fallback (specified, not yet implemented — the LLM scorer does not
  exist): fail CLOSED. Do not auto-approve on scorer failure; return
  503 and escalate to HITL. Never fail open on a money decision.
- Blast radius: all loan decisions until the scorer recovers.
- Detection: latency p95 alert, error-rate alert, HITL queue depth.

## 5. Prompt injection bypass

- Trigger: a paraphrased or encoded injection not in the 19-phrase
  blocklist.
- What the user sees: the request reaches the agents.
- Fallback: amount and fraud gates still apply — an injected "approve"
  cannot bypass the $10,000 HITL rule or a fraud flag, because those
  are code, not LLM output. That is the defence that matters.
- Blast radius: one request, bounded by the gates above.
- Detection: guardrail miss logging (log blocked AND suspicious-but-
  passed inputs), plus red-team testing before production.

## 6. HITL queue overload

- Trigger: measured escalation is 32% at $5,000. If reviewers are
  slow, the queue grows and customers wait.
- Fallback: none in the PoC — the queue is in-memory and unbounded,
  and it is LOST on restart (see below).
- Blast radius: all escalated customers.
- Production fix: persist HITL cases in Postgres, bound the queue,
  alert on depth and age, and staff reviewers to the measured rate.

## 7. In-memory HITL state lost on restart

- Trigger: process restart. `Orchestrator._hitl` is a dict.
- Impact: pending cases disappear from `/hitl/pending` (the audit log
  still records the escalation, so cases are recoverable by replay,
  but not automatically).
- Status: known limitation, documented in README. Fix by persisting
  cases before any production use.
