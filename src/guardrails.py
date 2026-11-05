"""Guardrails: prompt-injection blocklist + input validation.

Design (see ADR-004): a deterministic blocklist is the ONLY guardrail
shipped in this PoC. It is testable offline and its block rate is
measured in docs/MEASUREMENTS.md. It is NOT claimed to block 100% of
injection — no blocklist can. A production system must add an LLM
firewall (e.g. Lakera), output validation, and red-teaming; see
docs/FAILURE_MODES.md.
"""
import re

# Case-insensitive substrings. Each entry is a known injection pattern
# from the OWASP Top 10 for LLM Applications test corpus.
BLOCKED_PHRASES = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "disregard all previous",
    "override previous instructions",
    "you are now",
    "new instructions:",
    "system prompt",
    "reveal your instructions",
    "approve the loan",
    "approve this loan",
    "set risk score to 0",
    "set risk score to zero",
    "mark as low risk",
    "bypass fraud check",
    "skip fraud check",
    "do not flag",
    "jailbreak",
    "dan mode",
]

# Normalise: lowercase, collapse whitespace, strip punctuation runs.
_WS = re.compile(r"\s+")


def _normalise(text):
    return _WS.sub(" ", str(text).lower()).strip()


def check_text(text):
    """Return (blocked: bool, matched_phrase: str|None)."""
    norm = _normalise(text or "")
    for phrase in BLOCKED_PHRASES:
        if phrase in norm:
            return True, phrase
    return False, None


class ValidationError(ValueError):
    pass


def validate_loan_application(payload):
    """Validate a loan application dict. Raises ValidationError."""
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object")
    amount = payload.get("amount")
    if amount is None:
        raise ValidationError("amount is required")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("amount must be a number")
    if amount <= 0:
        raise ValidationError("amount must be positive")
    if amount > 1_000_000:
        raise ValidationError("amount exceeds maximum of 1000000")
    term = payload.get("term_months", 12)
    try:
        term = int(term)
    except (TypeError, ValueError):
        raise ValidationError("term_months must be an integer")
    if not 1 <= term <= 360:
        raise ValidationError("term_months must be between 1 and 360")
    customer_id = payload.get("customer_id")
    if not customer_id or not str(customer_id).strip():
        raise ValidationError("customer_id is required")
    # Free-text notes are scanned for injection; a hit blocks the request.
    notes = payload.get("notes", "")
    blocked, phrase = check_text(notes)
    if blocked:
        raise ValidationError(f"blocked by guardrail: matched '{phrase}'")
    return {"customer_id": str(customer_id), "amount": amount,
            "term_months": term, "notes": str(notes)}


def validate_fraud_payload(payload):
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object")
    if not payload.get("customer_id"):
        raise ValidationError("customer_id is required")
    notes = payload.get("notes", "")
    blocked, phrase = check_text(notes)
    if blocked:
        raise ValidationError(f"blocked by guardrail: matched '{phrase}'")
    return payload
