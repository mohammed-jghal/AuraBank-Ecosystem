# Loan Policy

## Approval rule

A loan is approved only when the credit score is at least 650 and the
monthly payment is at most 40 percent of monthly income. A score below
550 is declined. Scores between 550 and 649 go to manual review.

## Human in the loop

Any loan above 10000 dollars must be reviewed by a human supervisor,
even when the credit score is high. Low confidence below 0.60 also
forces human review. The threshold is configurable in src/config.py.

## Affordability

Monthly payment is estimated as amount divided by term in months.
Affordability fails when the payment exceeds 40 percent of monthly
income. Unaffordable applications are declined, not escalated.

## Audit

Every loan decision is written to the audit log with the credit score,
confidence, amount, and request id. No decision is taken without an
audit entry.
