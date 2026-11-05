"""Flask API for the AuraBank PoC.

Endpoints:
  GET  /health          readiness (policies + customers loadable)
  GET  /version         service + config version
  POST /onboard         validate + store a synthetic customer profile
  POST /loan/apply      orchestrated loan decision (Loan + Fraud + HITL)
  POST /fraud/check     fraud assessment only
  GET  /hitl/pending    list pending HITL cases
  POST /hitl/review     approve/decline a pending case
Every response carries request_id and latency_ms. All customer data in
this PoC is synthetic (seeded, zero PII) — see data/README.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from flask import Flask, g, jsonify, request

from . import config
from .agents import fraud_assessment
from .guardrails import ValidationError, validate_fraud_payload
from .log import write_audit
from .orchestrator import Orchestrator

BASE = Path(os.getenv("APP_HOME", Path(__file__).resolve().parents[1])).resolve()


def load_customers():
    path = config.CUSTOMER_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {c["customer_id"]: c for c in data}


def create_app(test_config=None):
    app = Flask(__name__)
    orch = Orchestrator()
    app.config["ORCHESTRATOR"] = orch
    app.config["CUSTOMERS"] = load_customers()
    if test_config:
        app.config.update(test_config)
        if "ORCHESTRATOR" in test_config:
            orch = test_config["ORCHESTRATOR"]

    @app.before_request
    def _rid():
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.started = time.perf_counter()

    @app.after_request
    def _headers(resp):
        resp.headers["X-Request-ID"] = g.get("request_id", "unknown")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def _lat():
        return round((time.perf_counter() - g.started) * 1000, 2)

    @app.get("/health")
    def health():
        ok = config.POLICY_DIR.exists() and bool(app.config["CUSTOMERS"])
        return jsonify({"status": "ready" if ok else "degraded",
                        "service": "aurabank-poc",
                        "version": config.CONFIG_VERSION,
                        "request_id": g.request_id,
                        "latency_ms": _lat()}), 200 if ok else 503

    @app.get("/version")
    def version():
        return jsonify({"service": "aurabank-poc",
                        "version": config.CONFIG_VERSION,
                        "hitl_threshold": config.HITL_AMOUNT_THRESHOLD,
                        "request_id": g.request_id,
                        "latency_ms": _lat()})

    @app.post("/onboard")
    def onboard():
        body = request.get_json(silent=True) or {}
        cid = body.get("customer_id")
        if not cid:
            return jsonify({"error": {"code": "invalid_request",
                                     "message": "customer_id is required",
                                     "request_id": g.request_id}}), 400
        app.config["CUSTOMERS"][cid] = body
        write_audit({"request_id": g.request_id, "agent": "onboarding",
                     "action": "onboarded", "confidence": 1.0,
                     "customer_id": cid}, config.LOG_DIR)
        return jsonify({"customer_id": cid, "status": "onboarded",
                        "request_id": g.request_id,
                        "latency_ms": _lat()}), 201

    @app.post("/loan/apply")
    def loan_apply():
        body = request.get_json(silent=True) or {}
        cid = body.get("customer_id")
        customer = app.config["CUSTOMERS"].get(cid) if cid else None
        if cid and customer is None:
            return jsonify({"error": {"code": "unknown_customer",
                                     "message": f"no customer {cid}",
                                     "request_id": g.request_id}}), 404
        # Allow inline customer data for testing (synthetic only).
        customer = customer or body.get("customer", {})
        if not customer:
            return jsonify({"error": {"code": "invalid_request",
                                     "message": "customer_id or customer required",
                                     "request_id": g.request_id}}), 400
        try:
            result = orch.process_loan(customer, body)
        except ValidationError as exc:
            return jsonify({"error": {"code": "validation_error",
                                     "message": str(exc),
                                     "request_id": g.request_id}}), 400
        result["latency_ms"] = _lat()
        return jsonify(result), 200

    @app.post("/fraud/check")
    def fraud_check():
        body = request.get_json(silent=True) or {}
        try:
            validate_fraud_payload(body)
        except ValidationError as exc:
            return jsonify({"error": {"code": "validation_error",
                                     "message": str(exc),
                                     "request_id": g.request_id}}), 400
        cid = body.get("customer_id")
        customer = app.config["CUSTOMERS"].get(cid, {}) if cid else {}
        txn = body.get("transaction", {}) or {}
        txn.setdefault("amount", body.get("amount", 0))
        res = fraud_assessment(customer, txn)
        write_audit({"request_id": g.request_id, "agent": "fraud_agent",
                     "action": "flagged" if res["flagged"] else "clear",
                     "confidence": res["confidence"],
                     "risk_score": res["risk_score"]}, config.LOG_DIR)
        return jsonify({**res, "request_id": g.request_id,
                        "latency_ms": _lat()}), 200

    @app.get("/hitl/pending")
    def hitl_pending():
        return jsonify({"pending": orch.hitl_pending,
                        "count": len(orch.hitl_pending),
                        "request_id": g.request_id,
                        "latency_ms": _lat()}), 200

    @app.post("/hitl/review")
    def hitl_review():
        body = request.get_json(silent=True) or {}
        case = orch.hitl_review(body.get("case_id"), body.get("reviewer", "supervisor"),
                                bool(body.get("approved", False)),
                                body.get("note", ""))
        if case is None:
            return jsonify({"error": {"code": "not_found",
                                     "message": "case not found",
                                     "request_id": g.request_id}}), 404
        return jsonify({**case, "request_id": g.request_id,
                        "latency_ms": _lat()}), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
