# ADR-003 — HITL threshold: $10,000, plus fraud and confidence gates

Status: Accepted (PoC 0.1.0) · Date: 2026-11-05

## Context

The document mandates human review for transactions above $10,000.
The threshold value itself is never justified in the document.

## Decision

Keep $10,000 as the amount threshold (configurable in `src/config.py`
as `HITL_AMOUNT_THRESHOLD`), AND escalate on two further gates that
the document does not make explicit:

1. Fraud risk >= 80 escalates at ANY amount (a $1,000 fraud is still fraud).
2. Loan confidence < 0.60 escalates even when the score and amount
   would auto-decide (uncertainty is itself a risk signal).
3. A loan-agent `manual_review` verdict (score 550-649) escalates.

Declines do NOT escalate: declining is the safe action, and sending
every decline to a human would drown reviewers (measured: 28/100
declined at $5,000; escalating those too would raise HITL load from
32% to 60%).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Threshold $1,000 | HITL load explodes; reviewers become the bottleneck and start rubber-stamping — the failure mode HITL exists to prevent |
| Threshold $50,000 | Lets $10k-$50k hallucinations auto-approve; the blast radius per error is 5x the chosen threshold |
| Amount-only gating | Misses fraud and low-confidence cases entirely |
| Escalate declines too | Doubles reviewer load with no safety gain; a wrongly declined customer can re-apply, a wrongly approved loan cannot be un-lent |

## Consequences

- Measured HITL rate at $5,000 is 32/100 (fraud + low confidence +
  manual review); at $15,000 it is 100% by amount alone (tested).
- The $10,000 figure remains an assumption: it is a business policy
  choice, not a measured optimum. A Staff-level follow-up is to tune
  it from the cost of a false approval vs the cost of reviewer time.
