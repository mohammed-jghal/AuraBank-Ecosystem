"""Orchestrator: a small explicit state machine (see ADR-001).

States: RECEIVED -> GUARDRAILS -> RAG -> LOAN_AGENT -> FRAUD_AGENT
        -> DECISION -> (AUTO | HITL_PENDING | DECLINED)
No LangGraph, no hidden control flow: every transition is a named
function, every transition is audit-logged, and the whole flow is
unit-testable without a network or an LLM key.

Decision rules (single place, see ADR-003):
  * guardrail block          -> rejected (blocked), no agent runs
  * fraud flagged (>=80)     -> HITL, whatever the loan decision
  * amount > $10,000         -> HITL, whatever the loan decision
  * confidence < 0.60        -> HITL
  * loan decision approved   -> auto-approved (only if none of the above)
  * loan decision declined   -> declined (no HITL: declining is safe)
  * loan decision manual_review -> HITL
"""
import time
import uuid

from . import config
from .agents import DeterministicScorer, fraud_assessment, loan_decision
from .guardrails import check_text, validate_loan_application
from .log import write_audit
from .rag import PolicyStore


class Orchestrator:
    def __init__(self, policy_dir=None, log_dir=None, scorer=None):
        self.policy_dir = policy_dir or config.POLICY_DIR
        self.log_dir = log_dir or config.LOG_DIR
        self.scorer = scorer or DeterministicScorer()
        self.store = PolicyStore(self.policy_dir)
        self._hitl = {}  # case_id -> case dict (in-memory; see HITL notes)

    # -- HITL store ----------------------------------------------------
    @property
    def hitl_pending(self):
        return [c for c in self._hitl.values() if c["status"] == "pending"]

    def hitl_review(self, case_id, reviewer, approved, note=""):
        case = self._hitl.get(case_id)
        if case is None:
            return None
        case["status"] = "approved" if approved else "declined"
        case["reviewed_by"] = reviewer
        case["review_note"] = note
        write_audit({"request_id": case["request_id"], "agent": "hitl",
                     "action": case["status"], "confidence": 1.0,
                     "case_id": case_id, "reviewer": reviewer},
                    self.log_dir)
        return case

    # -- Main flow ------------------------------------------------------
    def process_loan(self, customer, payload):
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        # 1. Validate + guardrails (fail fast, before any agent runs).
        try:
            clean = validate_loan_application(payload)
        except Exception as exc:  # ValidationError from guardrails
            write_audit({"request_id": request_id, "agent": "guardrails",
                         "action": "blocked", "confidence": 1.0,
                         "reason": str(exc)}, self.log_dir)
            return self._result(request_id, started, "blocked",
                                reason=str(exc))
        # Free-text notes were already scanned by validation; scan the
        # customer id / any extra text defensively as well.
        blocked, phrase = check_text(payload.get("notes", ""))
        if blocked:
            return self._result(request_id, started, "blocked",
                                reason=f"matched '{phrase}'")
        amount = clean["amount"]
        # 2. RAG: ground the decision in policy (retrieval, not recall).
        rag_hits = self.store.retrieve(
            f"loan approval credit score amount {amount}", top_k=config.RAG_TOP_K)
        # 3. Loan agent.
        loan = loan_decision(customer, amount, clean["term_months"],
                             scorer=self.scorer,
                             approve_threshold=config.CREDIT_APPROVE_THRESHOLD,
                             decline_threshold=config.CREDIT_DECLINE_THRESHOLD)
        write_audit({"request_id": request_id, "agent": "loan_agent",
                     "action": loan["decision"],
                     "confidence": loan["confidence"],
                     "credit_score": loan["credit_score"],
                     "amount": amount}, self.log_dir)
        # 4. Fraud agent. NOTE: the transaction amount here is the
        # customer's TYPICAL transaction size, not the loan amount —
        # using the loan amount ($5,000 vs a $50-300 average) would
        # fire the amount-spike signal for every applicant. The spike
        # signal is only meaningful on /fraud/check, where the caller
        # supplies a real transaction amount.
        txn = {"amount": float(customer.get("avg_tx_amount_30d", 0) or 0),
               "recent_international_tx": int(
                   customer.get("recent_international_tx", 0) or 0),
               "avg_tx_amount_30d": float(
                   customer.get("avg_tx_amount_30d", 0) or 0),
               "new_device": bool(customer.get("new_device", False)),
               "tx_last_hour": int(customer.get("tx_last_hour", 0) or 0),
               "txn_country": customer.get("home_country"),
               "amount_spike": False}
        fraud = fraud_assessment(customer, txn, scorer=self.scorer,
                                 flag_threshold=config.FRAUD_ESCALATION_THRESHOLD)
        write_audit({"request_id": request_id, "agent": "fraud_agent",
                     "action": "flagged" if fraud["flagged"] else "clear",
                     "confidence": fraud["confidence"],
                     "risk_score": fraud["risk_score"],
                     "signals": fraud["signals"]}, self.log_dir)
        # 5. Decision gateway (single place — ADR-003).
        reasons = []
        if fraud["flagged"]:
            reasons.append(f"fraud risk {fraud['risk_score']} >= "
                           f"{config.FRAUD_ESCALATION_THRESHOLD}")
        if amount > config.HITL_AMOUNT_THRESHOLD:
            reasons.append(f"amount {amount} > HITL threshold "
                           f"{config.HITL_AMOUNT_THRESHOLD}")
        if loan["confidence"] < config.LOW_CONFIDENCE_THRESHOLD:
            reasons.append(f"low confidence {loan['confidence']}")
        if loan["decision"] == "manual_review":
            reasons.append("loan agent requested manual review")
        if reasons:
            case_id = f"case-{request_id[:8]}"
            case = {"case_id": case_id, "request_id": request_id,
                    "customer_id": clean["customer_id"], "amount": amount,
                    "status": "pending", "reasons": reasons,
                    "loan": loan, "fraud": fraud}
            self._hitl[case_id] = case
            write_audit({"request_id": request_id, "agent": "orchestrator",
                         "action": "escalated_to_hitl", "confidence": 1.0,
                         "case_id": case_id, "reasons": reasons},
                        self.log_dir)
            return self._result(request_id, started, "pending_hitl",
                                case_id=case_id, reasons=reasons,
                                loan=loan, fraud=fraud, rag=rag_hits)
        if loan["decision"] == "approved":
            return self._result(request_id, started, "approved",
                                loan=loan, fraud=fraud, rag=rag_hits)
        return self._result(request_id, started, "declined",
                            loan=loan, fraud=fraud, rag=rag_hits)

    def _result(self, request_id, started, status, **extra):
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        out = {"request_id": request_id, "status": status,
               "latency_ms": latency_ms}
        out.update(extra)
        return out
