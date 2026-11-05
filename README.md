# AuraBank Ecosystem — PoC

A deterministic, testable Proof of Concept for a cloud-native
multi-agent retail-banking system: loan origination, fraud detection,
and human-in-the-loop review. Built to Staff-level depth: every number
below was measured by running the code in this repository, and every
claim from the Master Architecture Document that could not be measured
is labelled UNVERIFIED instead of repeated.

## What this is — and what it is not

**It is:** an Orchestrator (explicit state machine) + Loan Agent +
Fraud Agent + HITL, with RAG over local policy documents, guardrails,
and a full audit log. 100 synthetic customer profiles, zero PII.
40 tests, all passing. Flask API, Docker-ready.

**It is not:** a bank. There is no live LLM (the scorer is deterministic
rules with a pluggable interface), no live Core Banking System (customer
data is local JSON), no real customers, no regulatory approval, and no
production security (no auth, no TLS, no managed LLM firewall).
Do not deploy this against real money or real personal data.

## Architecture

```text
Client
  |
  v
Flask API (/loan/apply, /fraud/check, /hitl/*, /health, /version)
  |
  v
Orchestrator (state machine)
  |-- Guardrails (blocklist + validation) -- blocks before any agent runs
  |-- RAG (local TF-IDF over data/policies/*.md)
  |-- Loan Agent (deterministic credit score 300-850)
  |-- Fraud Agent (risk score 0-100, signals listed)
  |-- Decision Gateway (HITL if amount > $10,000, fraud >= 80,
  |                      confidence < 0.60, or manual review)
  v
Audit log (logs/audit.jsonl, JSONL, one entry per agent decision)
```

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
make install
make data        # generate 100 synthetic profiles (seed 42)
make test        # 40 tests
make measure     # regenerate docs/MEASUREMENTS.md with real numbers
PORT=8080 python run_app.py
```

```bash
curl -X POST http://127.0.0.1:8080/loan/apply \
  -H 'Content-Type: application/json' \
  -d '{"customer_id": "customer-001", "amount": 5000, "term_months": 12}'
curl http://127.0.0.1:8080/hitl/pending
curl http://127.0.0.1:8080/health
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Readiness (policies + customers loadable) |
| GET | `/version` | Service and config version |
| POST | `/onboard` | Register a synthetic customer profile |
| POST | `/loan/apply` | Orchestrated loan decision |
| POST | `/fraud/check` | Fraud assessment only |
| GET | `/hitl/pending` | List pending human-review cases |
| POST | `/hitl/review` | Approve / decline a pending case |

Every response carries `request_id` and `latency_ms`.

## Measured metrics (2026-11-05, reproduced by `python scripts/measure.py`)

Full method and per-payload tables: `docs/MEASUREMENTS.md`.

| Metric | Measured | Document claim |
|---|---:|---|
| Loan accuracy ($5,000 / 12 mo, 100 profiles) | **0.850** (TP 40, FP 0, TN 45, FN 15) | 99.5% — **UNVERIFIED** |
| Fraud precision / recall (threshold 80) | **1.000 / 1.000** (24/24) | >95% — **UNVERIFIED** (see below) |
| `/loan/apply` latency p50 / p95 | **0.7 ms / 1.0 ms** (local test client; varies slightly per run — reproduce with `make measure`) | <5 min origination — **UNVERIFIED** (decision step only, not end-to-end) |
| Prompt-injection block rate | **10/10** malicious blocked, 0/3 benign blocked | 100% — **CONTRADICTED by design** (a blocklist cannot block 100%) |
| HITL escalation ($5,000 loans) | **32/100** (40 approved, 28 declined) | — |

Fraud honesty note: precision/recall of 1.000 is **label leakage by
construction** — the synthetic fraud labels were built with the same
signals the scorer checks. It proves the pipeline works end to end;
it does NOT prove the detector generalises. A real figure needs
labelled production data this PoC does not have.

## Architecture Decision Records

- `docs/adr/ADR-001-orchestrator.md` — explicit state machine, not LangGraph
- `docs/adr/ADR-002-rag-store.md` — local TF-IDF, not Pinecone
- `docs/adr/ADR-003-hitl-threshold.md` — $10,000 + fraud + confidence gates
- `docs/adr/ADR-004-security-model.md` — blocklist guardrail, not an LLM firewall

Each ADR lists alternatives considered and why they were rejected,
with cost/latency tradeoffs.

## Failure modes

`docs/FAILURE_MODES.md` covers: hallucination under $10k, CBS mock
failure, RAG miss, LLM timeout (fail closed), injection bypass,
HITL queue overload, and in-memory HITL state lost on restart — with
fallback and blast radius for each.

## Known limitations (do not hide these)

- Synthetic data only; the document's 99.5% / <5 min / 100% claims are
  unproven here and are labelled as such in `docs/MEASUREMENTS.md`.
- HITL cases live in memory and are lost on restart (audit log survives).
- No CI workflow in the repo yet (GitHub API returns 403 for workflow
  paths — add `.github/workflows/ci.yml` via the web UI).
- Docker image not built in this environment (no docker binary here);
  the Dockerfile is present and untested — verify with `make docker`
  on a machine with Docker.
- No authentication, no TLS, no rate limiting, no PII encryption:
  the PoC stores no real PII, and must not be pointed at any.

## Repository map

- `src/` — config, guardrails, RAG, agents, orchestrator, Flask app, audit log
- `tests/` — 40 pytest tests (agents, guardrails, orchestrator/HITL, API, RAG)
- `data/policies/` — loan, fraud, KYC policy documents (RAG source)
- `data/customers.json` — 100 synthetic profiles, seed 42
- `scripts/` — `generate_data.py`, `measure.py`
- `docs/` — `MEASUREMENTS.md`, `FAILURE_MODES.md`, `adr/`
