"""General consumer pipeline tests: synthetic samples and reviewer-approved fixtures only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from consumer_dedup import DATASET_KIND, analyze
from consumer_report import build_demo, build_reviewed, demo_rows, write_report
import consumer_report_api


def reviewed_input():
    return {
        "schema_version": 1,
        "source": {"type": "first_party_general_product_reviews", "license": "owned",
                   "name": "Store-owned coffee reviews", "owner": "Mock merchant",
                   "reviewed_by": "Mock auditor", "reviewed_at": "2026-11-02T09:00:00Z"},
        "rows": [{"platform": "store", "post_id": "coffee-1", "author_id": "customer-1",
                  "product_id": "coffee", "posted_at": "2026-11-02",
                  "text": "This coffee is aromatic and the taste remains pleasantly balanced."},
                 {"platform": "store", "post_id": "coffee-2", "author_id": "customer-2",
                  "product_id": "coffee", "posted_at": "2026-11-02",
                  "text": "This coffee is aromatic and the taste remains pleasantly balanced."},
                 {"platform": "store", "post_id": "coffee-3", "author_id": "customer-3",
                  "product_id": "coffee", "posted_at": "2026-11-02",
                  "text": "I prefer this coffee because its taste is rather smooth and sweet."}]
    }


def encode(obj):
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()
    return data, hashlib.sha256(data).hexdigest()


def test_demo_metrics_exact_reproducible_and_stamped():
    a, b = build_demo(), build_demo()
    assert a == b
    assert a["dataset"]["mode"] == "demo"
    assert a["dataset"]["is_real_data"] is False
    assert a["dataset"]["existing_sns_pipeline_connected"] is False
    s = a["summary"]
    assert s == {
        "raw_input_rows": 282, "unique_post_ids": 280,
        "repeated_ingestion_rows": 2, "unique_content_groups": 212,
        "known_content_groups": 200, "unresolved_groups": 12,
        "repeated_content_posts": 68, "observed_accounts_not_people": 43, "products": 4
    }
    for p in a["products"]:
        assert p["observed_posts"] == 70
        assert p["content_groups"] == 53
        assert p["known_content_groups"] == 50
        assert p["unresolved_content_groups"] == 3
        assert p["removed_repeated_content_posts"] == 17
        assert p["verified_repost_edges"] == 10
        assert p["exact_text_join_edges"] == 7
        assert p["short_or_missing_text_posts"] == 13
        assert len(p["repeated_groups"]) == 10
        assert p["evidence_lower_bound"] == 50
        assert p["unresolved_upper_bound"] == 53


def test_report_has_no_original_reviews_or_author_identifiers():
    r = json.dumps(build_demo(), ensure_ascii=False)
    assert "Fresh roasted coffee aroma has" not in r
    assert "shopper-0" not in r
    assert "republisher-0" not in r
    assert '"same_person_inferred": false' in r
    assert '"existing_sns_pipeline_connected": false' in r


def test_exact_digest_required_and_reviews_not_saved(tmp_path):
    source, digest = encode(reviewed_input())
    with pytest.raises(ValueError, match="approved sha256 does not match"):
        build_reviewed(source, approved_sha256="0" * 64)
    r = build_reviewed(source, approved_sha256=digest)
    assert r["dataset"]["mode"] == "reviewed"
    assert r["summary"]["unique_post_ids"] == 3
    assert r["products"][0]["content_groups"] == 2
    target = tmp_path / "report.json"
    write_report(r, target)
    restored = json.loads(target.read_text())
    assert restored["dataset"]["sha256"] == digest
    assert "customer-1" not in target.read_text()
    assert "This coffee is aromatic" not in target.read_text()


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(schema_version=2),
    lambda x: x["source"].update(license="unknown"),
    lambda x: x["source"].update(type="existing_social_account_index"),
    lambda x: x["source"].update(reviewed_at="not-a-date"),
    lambda x: x["rows"][0].update(image_url="https://example.com/photo.jpg"),
    lambda x: x.update(rows=[]),
])
def test_reject_unreviewed_or_media_schema(mutation):
    x = reviewed_input()
    mutation(x)
    data, digest = encode(x)
    with pytest.raises(ValueError):
        build_reviewed(data, approved_sha256=digest)


def test_reject_oversized_and_invalid_digest():
    with pytest.raises(ValueError):
        build_reviewed(b"x" * 8_000_001, approved_sha256="0" * 64)
    with pytest.raises(ValueError):
        build_reviewed(b"{}", approved_sha256="invalid")


def test_group_ids_are_stable_and_not_a_person_id():
    rows = demo_rows()
    r = analyze(rows, dataset_kind=DATASET_KIND, with_groups=True)
    p = r["products"]["coffee"]
    groups = p["repeated_groups"]
    assert len(groups) == 10
    assert all(g["group_id"].startswith("C-") for g in groups)
    assert all(g["accounts"] in (2, 3) for g in groups)
    assert all(len(x) == 12 for g in groups for x in g["evidence_ids"])
    assert r["human_identity_inferred"] is False


def test_readonly_api_demo_is_public_only_for_synthetic(monkeypatch):
    monkeypatch.setenv("CONSUMER_REPORT_MODE", "demo")
    c = TestClient(consumer_report_api.app)
    assert c.get("/api/consumer/status").json()["is_real_data"] is False
    response = c.get("/api/consumer/summary")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["summary"]["products"] == 4
    assert c.get("/api/consumer/products/coffee").json()["product"]["content_groups"] == 53
    assert c.get("/api/consumer/products/not-found").status_code == 404
    assert c.post("/api/consumer/summary", json={}).status_code == 405


def test_real_api_requires_separate_token_and_report_path(monkeypatch, tmp_path):
    data, digest = encode(reviewed_input())
    report = build_reviewed(data, approved_sha256=digest)
    path = tmp_path / "reviewed.json"
    write_report(report, path)
    monkeypatch.setenv("CONSUMER_REPORT_MODE", "reviewed")
    monkeypatch.setenv("CONSUMER_REPORT_PATH", str(path))
    monkeypatch.setenv("CONSUMER_REPORT_READ_TOKEN", "x" * 48)
    c = TestClient(consumer_report_api.app)
    assert c.get("/api/consumer/summary").status_code == 401
    assert c.get("/api/consumer/summary", headers={"Authorization": "Bearer wrong"}).status_code == 401
    good = c.get("/api/consumer/summary", headers={"Authorization": "Bearer " + "x" * 48})
    assert good.status_code == 200
    assert good.json()["dataset"]["mode"] == "reviewed"
    assert good.json()["summary"]["unique_post_ids"] == 3


def test_real_api_fails_closed_for_missing_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("CONSUMER_REPORT_MODE", "reviewed")
    monkeypatch.setenv("CONSUMER_REPORT_PATH", str(tmp_path / "missing.json"))
    monkeypatch.delenv("CONSUMER_REPORT_READ_TOKEN", raising=False)
    c = TestClient(consumer_report_api.app)
    assert c.get("/api/consumer/summary").status_code == 503


def test_static_dashboard_isolated_and_accessible():
    html = (Path(__file__).parent / "consumer" / "index.html").read_text()
    assert 'lang="ko"' in html
    assert 'id="reportFile"' in html
    assert "demo-report.json" in html
    assert "계정" in html
    assert "social_sources" not in html
    assert "account_groups" not in html


def test_approved_report_cannot_appear_as_demo():
    data, digest = encode(reviewed_input())
    r = build_reviewed(data, approved_sha256=digest)
    assert r["dataset"]["is_real_data"] is True
    assert r["dataset"]["kind"] == "reviewed_general_products"


def test_public_editorial_api_is_licensed_and_not_consumer_demand():
    import consumer_report_api
    from fastapi.testclient import TestClient
    c=TestClient(consumer_report_api.app)
    response=c.get("/api/consumer/editorial")
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-store"
    data=response.json()
    assert data["dataset"]["kind"]=="real_editorial_product_ratings"
    assert data["dataset"]["license"]=="CC BY 4.0"
    assert data["dataset"]["is_consumer_demand"] is False
    assert data["summary"]["source_ratings_rows"]==8107
    assert data["summary"]["selected_products"]==36
    assert all("author_id" not in str(p) for p in data["products"])


def test_readonly_historical_session_aggregate_api():
    import consumer_report_api
    from fastapi.testclient import TestClient
    c = TestClient(consumer_report_api.app)
    response = c.get("/api/consumer/sessions")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    out = response.json()
    assert out["dataset"]["kind"] == "historical_real_ecommerce_sessions"
    assert out["dataset"]["is_current_data"] is False
    assert out["dataset"]["contains_person_identifiers"] is False
    assert out["summary"]["sessions"] == 12330
    assert out["summary"]["purchases"] == 1908
    assert c.post("/api/consumer/sessions").status_code == 405


def test_readonly_current_wikimedia_attention_api():
    import consumer_report_api
    from fastapi.testclient import TestClient
    c = TestClient(consumer_report_api.app)
    response = c.get("/api/consumer/attention")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["dataset"]["license"] == "CC0 1.0"
    assert body["dataset"]["is_demand"] is False
    assert body["dataset"]["is_purchases"] is False
    assert len(body["topics"]) == 6
    assert c.post("/api/consumer/attention").status_code == 405
