"""Read-only API for an *independent* general-consumer report.

Not a router for gateway.py. Does not import/serve the sensitive SNS corpus.
Demo mode is safe without credentials; reviewed-report mode requires a separate
high-entropy token and explicit path. No upload, feed, or account-link endpoint.
"""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from consumer_report import build_demo

app = FastAPI(title="General Product Demand Evidence", docs_url=None, redoc_url=None)


def _data(authorization: str | None = None) -> dict:
    mode = os.getenv("CONSUMER_REPORT_MODE", "demo")
    if mode == "demo":
        return build_demo()
    if mode != "reviewed":
        raise HTTPException(503, detail="invalid report mode")
    token = os.getenv("CONSUMER_REPORT_READ_TOKEN", "")
    path = os.getenv("CONSUMER_REPORT_PATH", "")
    if len(token) < 32 or not path:
        raise HTTPException(503, detail="reviewed-report API is not configured")
    if not authorization or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, detail="report authorization required")
    file_path = Path(path)
    try:
        if not file_path.is_file() or file_path.stat().st_size > 2_000_000:
            raise ValueError("report file missing or oversized")
        report = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(503, detail="report unavailable")
    if (not isinstance(report, dict) or report.get("schema_version") != 1
        or not isinstance(report.get("dataset"), dict)
        or report["dataset"].get("mode") != "reviewed"
        or report["dataset"].get("is_real_data") is not True
        or not isinstance(report.get("summary"), dict)
        or not isinstance(report.get("products"), list)):
        raise HTTPException(503, detail="report schema mismatch")
    return report


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    return response


@app.get("/api/consumer/status")
def status(authorization: str | None = Header(default=None)):
    report = _data(authorization)
    return {"mode": report["dataset"]["mode"], "products": report["summary"]["products"],
            "is_real_data": report["dataset"]["is_real_data"],
            "existing_sns_pipeline_connected": False}


@app.get("/api/consumer/summary")
def summary(authorization: str | None = Header(default=None)):
    return _data(authorization)


@app.get("/api/consumer/products/{product_id}")
def product(product_id: str, authorization: str | None = Header(default=None)):
    report = _data(authorization)
    for item in report["products"]:
        if item["product_id"] == product_id:
            return {"dataset": report["dataset"], "product": item}
    raise HTTPException(404, detail="product not found")


def _public_editorial() -> dict:
    """Only a bundled, licensed aggregate; not the existing SNS database."""
    file_path=Path(__file__).resolve().parent / "consumer" / "editorial-report.json"
    try:
        if not file_path.is_file() or file_path.stat().st_size>200_000:
            raise ValueError("editorial report absent or oversized")
        record=json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(503,detail="licensed editorial report unavailable")
    if (not isinstance(record,dict) or record.get("schema_version")!=1
        or record.get("dataset",{}).get("kind")!="real_editorial_product_ratings"
        or record.get("dataset",{}).get("is_consumer_demand") is not False
        or record.get("dataset",{}).get("license")!="CC BY 4.0"
        or not isinstance(record.get("products"),list)):
        raise HTTPException(503,detail="editorial report schema mismatch")
    return record


@app.get("/api/consumer/editorial")
def editorial():
    """Public general-goods editorial ratings; never individual review content."""
    return _public_editorial()


def _public_sessions() -> dict:
    """Historical CC BY4 aggregate only. No raw sessions, person IDs or SNS data."""
    file_path = Path(__file__).resolve().parent / "consumer" / "session-report.json"
    try:
        if not file_path.is_file() or file_path.stat().st_size > 100_000:
            raise ValueError("UCI aggregate unavailable or unexpectedly large")
        report = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(503, detail="historical session report unavailable")
    ds = report.get("dataset", {}) if isinstance(report, dict) else {}
    s = report.get("summary", {}) if isinstance(report, dict) else {}
    if (report.get("schema_version") != 1 or
        ds.get("kind") != "historical_real_ecommerce_sessions" or
        ds.get("is_current_data") is not False or
        ds.get("is_current_market_demand") is not False or
        ds.get("contains_person_identifiers") is not False or
        ds.get("license") != "CC BY 4.0" or
        s.get("sessions") != 12330 or s.get("purchases") != 1908):
        raise HTTPException(503, detail="historical session aggregate schema mismatch")
    return report


@app.get("/api/consumer/sessions")
def shopping_session_aggregates():
    """Read-only historical purchase-completion evidence, not live conversion."""
    return _public_sessions()


def _public_attention() -> dict:
    """Only six CC0 article view aggregates; not requests/people/SNS."""
    file_path = Path(__file__).resolve().parent / "consumer" / "attention-report.json"
    try:
        if not file_path.is_file() or file_path.stat().st_size > 60_000:
            raise ValueError("attention aggregate missing or too large")
        report = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(503, detail="attention report unavailable")
    data = report.get("dataset", {}) if isinstance(report, dict) else {}
    topics = report.get("topics", []) if isinstance(report, dict) else []
    if (report.get("schema_version") != 1 or
        data.get("kind") != "current_article_attention_not_demand" or
        data.get("license") != "CC0 1.0" or
        data.get("is_demand") is not False or
        data.get("is_purchases") is not False or
        data.get("contains_individuals") is not False or
        len(topics) != 6):
        raise HTTPException(503, detail="unexpected attention report schema")
    return report


@app.get("/api/consumer/attention")
def public_attention():
    """Wikimedia current aggregate pageviews; explicitly not sales demand."""
    return _public_attention()
