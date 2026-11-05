# Fraud Policy

## Risk scoring

Fraud risk is scored from 0 to 100. Signals include recent
international transactions, an amount spike above three times the
30-day average, a new device, high transaction velocity, a foreign
transaction country, and a new account under 30 days old.

## Escalation

A risk score of 80 or above flags the case and forces human review,
whatever the loan amount. Flagged cases are never auto-approved.

## Precision target

Fraud detection aims for high precision: a false positive blocks a
legitimate customer, so the threshold is set high at 80. Precision and
recall are measured on labelled synthetic cases in docs/MEASUREMENTS.md
and must be reported together, never precision alone.

## Audit

Every fraud assessment is logged with the risk score, the signals that
fired, and confidence. The signal list is the explanation for the
decision.
