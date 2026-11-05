"""JSONL audit logging with injectable directories for test isolation.

Every agent decision writes one entry: request_id, agent, action,
confidence, timestamp, and the inputs that drove the decision (amounts
and scores only — never raw PII, never free-text customer notes).
Tests write to tmp_path; production logs live in logs/ and are git-ignored.
"""
from datetime import datetime, timezone
import json
from pathlib import Path


def write_audit(event, log_dir="logs"):
    """Append one audit entry. Returns the entry dict."""
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        **event,
    }
    with (path / "audit.jsonl").open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry


def read_audit(log_dir="logs"):
    file = Path(log_dir) / "audit.jsonl"
    if not file.exists():
        return []
    return [
        json.loads(line)
        for line in file.read_text().splitlines()
        if line.strip()
    ]
