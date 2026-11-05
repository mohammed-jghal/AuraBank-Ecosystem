import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.agents import DeterministicScorer, fraud_assessment, loan_decision

PRIME = {"annual_income": 120000, "on_time_payment_ratio": 0.98,
         "employment_years": 10, "debt_to_income": 0.1,
         "savings_months": 12, "prior_defaults": 0,
         "home_country": "US", "account_age_days": 500}
SUBPRIME = {"annual_income": 20000, "on_time_payment_ratio": 0.5,
            "employment_years": 0, "debt_to_income": 0.8,
            "savings_months": 0, "prior_defaults": 3,
            "home_country": "US", "account_age_days": 500}


def test_credit_score_prime_high():
    s = DeterministicScorer().credit_score(PRIME)
    assert s["credit_score"] >= 650


def test_credit_score_subprime_low():
    s = DeterministicScorer().credit_score(SUBPRIME)
    assert s["credit_score"] < 550


def test_credit_score_clamped():
    s = DeterministicScorer().credit_score(
        {"annual_income": 10**9, "on_time_payment_ratio": 1.0,
         "employment_years": 50, "debt_to_income": 0.0,
         "savings_months": 100, "prior_defaults": 0})
    assert 300 <= s["credit_score"] <= 850


def test_loan_approve_prime():
    d = loan_decision(PRIME, 5000, 12)
    assert d["decision"] == "approved" and d["affordable"] is True


def test_loan_decline_subprime():
    d = loan_decision(SUBPRIME, 5000, 12)
    assert d["decision"] == "declined"


def test_loan_unaffordable_declined():
    d = loan_decision(PRIME, 500000, 12)
    assert d["decision"] == "declined" and d["affordable"] is False


def test_fraud_flag_stacked_signals():
    c = dict(PRIME, account_age_days=10)
    txn = {"recent_international_tx": 4, "avg_tx_amount_30d": 50,
           "amount": 50, "new_device": True, "tx_last_hour": 8,
           "txn_country": "GB"}
    r = fraud_assessment(c, txn)
    assert r["flagged"] is True and r["risk_score"] >= 80
    assert "international_tx" in r["signals"]


def test_fraud_clear_prime():
    txn = {"recent_international_tx": 0, "avg_tx_amount_30d": 200,
           "amount": 200, "new_device": False, "tx_last_hour": 1,
           "txn_country": "US"}
    r = fraud_assessment(PRIME, txn)
    assert r["flagged"] is False and r["risk_score"] < 80
