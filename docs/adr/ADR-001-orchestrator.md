# ADR-001 — Orchestrator: explicit state machine, not LangGraph

Status: Accepted (PoC 0.1.0) · Date: 2026-11-05

## Context

The Master Architecture Document specifies an orchestrator via LangGraph
for Loan, Fraud and Onboarding agents. The PoC flow is 5 steps:
guardrails → RAG → loan agent → fraud agent → decision gateway.

## Decision

Implement the orchestrator as an explicit Python state machine in
`src/orchestrator.py`. Each transition is a named code path, audit-logged,
and unit-testable without a network or an LLM key.

## Alternatives considered

| Alternative | Cost | Latency | Why rejected for the PoC |
|---|---:|---:|---|
| LangGraph | New dependency, graph runtime, checkpointing infra | +10-50 ms per step, plus serialisation | No benefit at 5 deterministic steps; hides control flow; makes offline tests depend on a framework |
| Temporal / workflow engine | Server + workers, operational burden | Network hop per step | Overkill for a single-process PoC; justified only at multi-service scale |
| LLM-driven routing (agent decides next step) | Token cost per hop, non-deterministic | +seconds per hop | Untestable routing; a routing hallucination can skip the fraud agent — unacceptable in banking |
| Simple router function | $0 | ~0 ms | Accepted in effect: the state machine IS a router, with named states instead of implicit ifs |

## Consequences

- Positive: deterministic, 40 tests run in <1 s, every decision is
  reproducible from the same input.
- Negative: adding a 4th agent requires editing the state machine by
  hand. Acceptable at PoC scale; revisit when agents exceed ~6 or when
  steps become conditional on LLM output.
- Reversal condition: adopt LangGraph when the flow needs dynamic
  branching, long-running checkpoints, or human-in-the-loop persistence
  across restarts (today HITL state is in-memory — see FAILURE_MODES).
