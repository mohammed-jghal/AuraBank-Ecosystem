import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.app import create_app


def _client(tmp_path):
    import src.config as cfg
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health(tmp_path):
    c = _client(tmp_path)
    r = c.get("/health")
    assert r.status_code == 200 and r.json["status"] == "ready"
    assert "request_id" in r.json and "latency_ms" in r.json


def test_version(tmp_path):
    c = _client(tmp_path)
    r = c.get("/version")
    assert r.status_code == 200 and r.json["version"] == "0.1.0"


def test_loan_apply_approved(tmp_path):
    c = _client(tmp_path)
    r = c.post("/loan/apply", json={"customer_id": "customer-001",
                                    "amount": 5000, "term_months": 12})
    assert r.status_code == 200
    assert r.json["status"] in ("approved", "pending_hitl", "declined")
    assert "request_id" in r.json


def test_loan_apply_unknown_customer(tmp_path):
    c = _client(tmp_path)
    r = c.post("/loan/apply", json={"customer_id": "customer-999",
                                    "amount": 5000})
    assert r.status_code == 404


def test_loan_apply_invalid_amount(tmp_path):
    c = _client(tmp_path)
    r = c.post("/loan/apply", json={"customer_id": "customer-001",
                                    "amount": -1})
    assert r.status_code == 200  # orchestrator returns blocked, not crash
    assert r.json["status"] == "blocked"


def test_fraud_check(tmp_path):
    c = _client(tmp_path)
    r = c.post("/fraud/check", json={"customer_id": "customer-001",
                                     "transaction": {"amount": 100}})
    assert r.status_code == 200 and "risk_score" in r.json


def test_hitl_flow_via_api(tmp_path):
    c = _client(tmp_path)
    r = c.post("/loan/apply", json={"customer_id": "customer-001",
                                    "amount": 50000, "term_months": 12})
    assert r.status_code == 200 and r.json["status"] == "pending_hitl"
    case_id = r.json["case_id"]
    p = c.get("/hitl/pending")
    assert p.json["count"] >= 1
    rev = c.post("/hitl/review", json={"case_id": case_id,
                                       "reviewer": "supervisor-1",
                                       "approved": True})
    assert rev.status_code == 200 and rev.json["status"] == "approved"


def test_onboard(tmp_path):
    c = _client(tmp_path)
    r = c.post("/onboard", json={"customer_id": "customer-900",
                                 "home_country": "US"})
    assert r.status_code == 201
