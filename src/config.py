"""Runtime configuration. All values overridable via environment variables.

Staff-level note: every threshold that changes a customer outcome is a
named constant here, not a magic number buried in agent code. Changing a
threshold is a config change, reviewable in one place, and auditable in
the decision log (the effective config version is recorded per decision).
"""
import os
from pathlib import Path

BASE = Path(os.getenv("APP_HOME", Path(__file__).resolve().parents[1])).resolve()
CONFIG_VERSION = "0.1.0"

# Human-in-the-loop: any loan above this amount (USD) MUST go to a human.
HITL_AMOUNT_THRESHOLD = float(os.getenv("HITL_AMOUNT_THRESHOLD", "10000"))
# Fraud risk above this score (0-100) MUST go to a human, any amount.
FRAUD_ESCALATION_THRESHOLD = int(os.getenv("FRAUD_ESCALATION_THRESHOLD", "80"))
# Loan approval: credit score at or above this approves (subject to HITL/fraud).
CREDIT_APPROVE_THRESHOLD = int(os.getenv("CREDIT_APPROVE_THRESHOLD", "650"))
# Below this score the loan is declined outright (no HITL — see ADR-003).
CREDIT_DECLINE_THRESHOLD = int(os.getenv("CREDIT_DECLINE_THRESHOLD", "550"))
# Confidence below this forces HITL even when score/amount would auto-decide.
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.60"))
# Maximum loan amount the API will accept at all.
MAX_LOAN_AMOUNT = float(os.getenv("MAX_LOAN_AMOUNT", "1000000"))
# Maximum forecast/request horizon is N/A here; max loan term in months.
MAX_TERM_MONTHS = int(os.getenv("MAX_TERM_MONTHS", "360"))
# Prompt-injection / guardrail policy version (recorded in audit log).
GUARDRAIL_POLICY_VERSION = "guardrails-0.1.0"
# RAG retrieval: how many policy chunks to return per query.
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
# Paths (overridable for tests).
POLICY_DIR = Path(os.getenv("POLICY_DIR", BASE / "data" / "policies"))
CUSTOMER_FILE = Path(os.getenv("CUSTOMER_FILE", BASE / "data" / "customers.json"))
LOG_DIR = Path(os.getenv("LOG_DIR", BASE / "logs"))
