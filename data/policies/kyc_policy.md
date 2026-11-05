# KYC Policy

## Identity

Onboarding requires a customer id and a home country. Synthetic
profiles in this PoC carry no real personal data: names are generated
identifiers such as customer-001, and no national ids, addresses, or
phone numbers are stored.

## Data minimisation

Only the fields needed for credit and fraud scoring are stored:
income, employment years, payment history, debt ratio, savings,
account age, and recent transaction counters. Free-text notes are
scanned by guardrails and are never stored in the audit log.

## Retention

Audit logs record scores and decisions, not personal data. Logs are
local JSONL files and are excluded from version control.
