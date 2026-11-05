import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.rag import PolicyStore

ROOT = Path(__file__).parents[1]


def test_retrieve_loan_policy():
    s = PolicyStore(ROOT / "data" / "policies")
    hits = s.retrieve("loan approval credit score 650", top_k=3)
    assert hits
    assert any(h["source"] == "loan_policy.md" for h in hits)


def test_retrieve_fraud_policy():
    s = PolicyStore(ROOT / "data" / "policies")
    hits = s.retrieve("fraud risk score 80 escalation", top_k=3)
    assert hits
    assert any(h["source"] == "fraud_policy.md" for h in hits)


def test_retrieve_miss_returns_empty():
    s = PolicyStore(ROOT / "data" / "policies")
    assert s.retrieve("quantum entanglement zebra", top_k=3) == []


def test_retrieve_empty_dir(tmp_path):
    s = PolicyStore(tmp_path)
    assert s.retrieve("loan", top_k=3) == []
