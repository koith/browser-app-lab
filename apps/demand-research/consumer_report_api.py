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

from fastapi import FastAPI, Header, HTTPException, Response

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
        or report.get("dataset", {}).get("mode") != "reviewed"
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
