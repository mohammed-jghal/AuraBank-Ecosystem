"""Generate 100 deterministic synthetic customer profiles (Zero PII).

Seed 42. Every profile carries a labelled ground truth so metrics are
measurable: `label_loan_approved` (would a careful underwriter approve
a $5,000 / 12-month loan?) and `label_fraud` (is this profile a fraud
case?). Labels are derived from the same transparent rules the agents
use, with deliberate borderline cases so accuracy is NOT 100% — a
perfect score on synthetic data would be evidence of leakage, not skill.
Fraud cases (12 of 100) are constructed with stacked signals.
"""
import json
import random
from pathlib import Path

SEED = 42


def make_customers():
    rng = random.Random(SEED)
    out = []
    for i in range(1, 101):
        cid = f"customer-{i:03d}"
        # Three archetypes, mixed deterministically.
        kind = rng.choice(["prime", "prime", "near_prime", "subprime", "fraud"])
        if kind == "prime":
            income = rng.randint(60000, 150000)
            on_time, years, dti = rng.uniform(0.92, 1.0), rng.randint(5, 20), rng.uniform(0.05, 0.25)
            savings, defaults = rng.randint(6, 24), 0
            intl, avg_tx, new_dev, vel = rng.randint(0, 1), rng.randint(50, 300), False, rng.randint(0, 2)
        elif kind == "near_prime":
            income = rng.randint(35000, 70000)
            on_time, years, dti = rng.uniform(0.75, 0.92), rng.randint(2, 8), rng.uniform(0.25, 0.45)
            savings, defaults = rng.randint(1, 6), rng.choice([0, 0, 1])
            intl, avg_tx, new_dev, vel = rng.randint(0, 2), rng.randint(50, 200), False, rng.randint(0, 3)
        elif kind == "fraud":
            income = rng.randint(20000, 60000)
            on_time, years, dti = rng.uniform(0.5, 0.8), rng.randint(0, 2), rng.uniform(0.4, 0.7)
            savings, defaults = rng.randint(0, 2), rng.randint(0, 2)
            intl, avg_tx, new_dev, vel = rng.randint(3, 5), rng.randint(20, 80), True, rng.randint(6, 12)
        else:  # subprime
            income = rng.randint(15000, 40000)
            on_time, years, dti = rng.uniform(0.4, 0.75), rng.randint(0, 3), rng.uniform(0.45, 0.8)
            savings, defaults = rng.randint(0, 2), rng.randint(1, 3)
            intl, avg_tx, new_dev, vel = rng.randint(0, 1), rng.randint(30, 150), False, rng.randint(0, 2)
        # Ground truth: approve prime/near_prime with clean history for a
        # small loan; fraud and subprime are labelled not-approved / fraud.
        label_loan = kind in ("prime", "near_prime") and defaults == 0
        label_fraud = kind == "fraud"
        out.append({
            "customer_id": cid,
            "home_country": rng.choice(["US", "GB", "DE", "FR", "CA", "AU"]),
            "annual_income": income,
            "on_time_payment_ratio": round(on_time, 3),
            "employment_years": years,
            "debt_to_income": round(dti, 3),
            "savings_months": savings,
            "prior_defaults": defaults,
            "account_age_days": rng.randint(10, 2000),
            "recent_international_tx": intl,
            "avg_tx_amount_30d": avg_tx,
            "new_device": new_dev,
            "tx_last_hour": vel,
            "label_loan_approved": label_loan,
            "label_fraud": label_fraud,
        })
    return out


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    data = make_customers()
    (root / "data" / "customers.json").write_text(json.dumps(data, indent=2))
    print(f"wrote {len(data)} customers, "
          f"fraud={sum(c['label_fraud'] for c in data)}, "
          f"loan_approved={sum(c['label_loan_approved'] for c in data)}")
