"""Loan Agent and Fraud Agent — deterministic, testable scorers.

LLM interface (pluggable): both agents take a `scorer` object with a
single method. The default scorer is a transparent rule-based model
whose formula is documented below and whose outputs are reproducible.
A future LLM scorer must implement the same interface and return the
same shape; swapping it in is a one-line change in orchestrator.py.
No live LLM call is made in this PoC and no API key is required.

Credit-score formula (transparent, 300-850 scale):
  base 300
  + income: up to +150 (log-scaled, capped at $150k)
  + payment history: on-time ratio * 150
  + employment years: up to +100 (10+ years)
  + debt-to-income: -200 * dti (0.0-1.0), i.e. high debt penalised
  + savings buffer: up to +50 (months of expenses covered, capped 12)
  + prior defaults: -100 each, capped at -200
Result is clamped to [300, 850]. Confidence is 0.55-0.95, lower when
inputs are sparse (missing fields) or the score is near a threshold.

Fraud risk (0-100):
  +25 per recent international transaction beyond 1
  +20 if amount > 3x the customer's 30-day average transaction
  +15 if a new device was used
  +15 if velocity (tx in last hour) > 5
  +10 if the transaction country differs from the home country
  +10 if the account is < 30 days old
Capped at 100. Confidence is higher when more signals are present.
"""
import math


class DeterministicScorer:
    """Default scorer. Pure functions of the customer dict — no I/O."""

    def credit_score(self, customer):
        income = float(customer.get("annual_income", 0) or 0)
        on_time = float(customer.get("on_time_payment_ratio", 0.8) or 0.8)
        years = float(customer.get("employment_years", 0) or 0)
        dti = float(customer.get("debt_to_income", 0.3) or 0.3)
        savings_months = float(customer.get("savings_months", 0) or 0)
        defaults = int(customer.get("prior_defaults", 0) or 0)
        score = 300.0
        score += 150.0 * min(math.log1p(income / 10000.0) / math.log1p(15.0), 1.0)
        score += 150.0 * max(0.0, min(on_time, 1.0))
        score += 100.0 * min(years / 10.0, 1.0)
        score -= 200.0 * max(0.0, min(dti, 1.0))
        score += 50.0 * min(savings_months / 12.0, 1.0)
        score -= 100.0 * min(defaults, 2)
        score = max(300.0, min(850.0, score))
        # Confidence: sparse inputs or a score near a decision boundary
        # lower confidence, which is what forces HITL (see ADR-003).
        missing = sum(
            1 for k in ("annual_income", "on_time_payment_ratio",
                        "employment_years", "debt_to_income")
            if customer.get(k) is None
        )
        confidence = 0.95 - 0.08 * missing
        for boundary in (550, 650):
            if abs(score - boundary) < 25:
                confidence -= 0.10
        return {"credit_score": round(score, 1),
                "confidence": round(max(0.55, min(0.95, confidence)), 2)}

    def fraud_risk(self, customer, txn):
        risk = 0
        signals = []
        intl = int(txn.get("recent_international_tx", 0) or 0)
        if intl > 1:
            risk += 25 * min(intl - 1, 2)
            signals.append("international_tx")
        avg = float(txn.get("avg_tx_amount_30d", 0) or 0)
        amount = float(txn.get("amount", 0) or 0)
        if avg > 0 and amount > 3 * avg:
            risk += 20
            signals.append("amount_spike")
        if txn.get("new_device"):
            risk += 15
            signals.append("new_device")
        if int(txn.get("tx_last_hour", 0) or 0) > 5:
            risk += 15
            signals.append("high_velocity")
        if txn.get("txn_country") and customer.get("home_country") \
                and txn["txn_country"] != customer["home_country"]:
            risk += 10
            signals.append("foreign_country")
        if int(customer.get("account_age_days", 365) or 365) < 30:
            risk += 10
            signals.append("new_account")
        risk = min(100, risk)
        confidence = round(0.60 + 0.05 * len(signals), 2)
        return {"risk_score": risk, "signals": signals,
                "confidence": min(0.95, confidence)}


def loan_decision(customer, amount, term_months, scorer=None,
                  approve_threshold=650, decline_threshold=550):
    """Return a loan decision dict. Does NOT apply the HITL gate —
    the orchestrator owns that (single place where escalation is decided).
    """
    scorer = scorer or DeterministicScorer()
    res = scorer.credit_score(customer)
    score, conf = res["credit_score"], res["confidence"]
    income = float(customer.get("annual_income", 0) or 0)
    # Affordability: monthly payment estimate must be < 40% of monthly income.
    monthly_payment = amount / max(term_months, 1) if term_months else amount
    affordable = income > 0 and monthly_payment <= 0.40 * (income / 12.0)
    if score >= approve_threshold and affordable:
        decision = "approved"
    elif score < decline_threshold or not affordable:
        decision = "declined"
    else:
        decision = "manual_review"
    return {"decision": decision, "credit_score": score,
            "confidence": conf, "affordable": affordable,
            "amount": amount, "term_months": term_months}


def fraud_assessment(customer, txn, scorer=None, flag_threshold=80):
    scorer = scorer or DeterministicScorer()
    res = scorer.fraud_risk(customer, txn)
    return {"flagged": res["risk_score"] >= flag_threshold,
            "risk_score": res["risk_score"], "signals": res["signals"],
            "confidence": res["confidence"]}
