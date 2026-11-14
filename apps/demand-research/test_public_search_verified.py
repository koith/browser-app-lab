"""Synthetic, network-free proof that public Markdown cannot forge a post.

Production Render endpoint can expose only posts whose URI, DID, exact body,
date and original text match official Bluesky AppView responses.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

import public_search_verified as v


class Response:
    status = 200
    def __init__(self, body):
        self.body = body.encode("utf-8")
    def read(self, n=-1):
        return self.body[:n] if n > 0 else self.body
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


def test_official_verification_is_required(monkeypatch):
    now = datetime.now(timezone.utc)
    did = "did:plc:aaaaaaaaaaaaaaaaaaaaaaaa"
    uri = f"at://{did}/app.bsky.feed.post/3n275awaudk2f"
    calls = []
    forged = {"value": False}

    def fake_open(req, timeout=10):
        url = req.full_url
        calls.append(url)
        if url.startswith(v.SEARCH):
            return Response(
                "[View on Bluesky](https://bsky.app/profile/sample.bsky.social/post/3n275awaudk2f)\n"
                "UNTRUSTED FAKE BODY")
        if url.startswith(v.PROFILES):
            return Response(json.dumps({"profiles":[
                {"handle":"sample.bsky.social","did":did}
            ]}))
        if url.startswith(v.POSTS):
            return Response(json.dumps({"posts":[{
                "uri":uri if not forged["value"] else
                    "at://did:plc:bbbbbbbbbbbbbbbbbbbbbbbb/app.bsky.feed.post/3n275awaudk2f",
                "author":{"did":did,"handle":"sample.bsky.social"},
                "record":{"text":"뒷계 official verified original",
                          "createdAt":now.isoformat()},
                "likeCount":0,"replyCount":0,
            }]}))
        raise AssertionError("Unexpected host requested")
    monkeypatch.setattr(v, "urlopen", fake_open)
    start = (now - timedelta(days=1)).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
    ok = v._query("뒷계", start, end)
    assert len(ok)==1
    assert ok[0]["uri"]==uri
    assert "UNTRUSTED FAKE BODY" not in json.dumps(ok,ensure_ascii=False)
    forged["value"] = True
    assert v._query("뒷계",start,end)==[]
    assert any(q.startswith(v.SEARCH) for q in calls)
    assert any(q.startswith(v.PROFILES) for q in calls)
    assert any(q.startswith(v.POSTS) for q in calls)


def test_endpoint_rejects_unbounded_and_unsupported_queries():
    app=FastAPI()
    app.include_router(v.router)
    client=TestClient(app)
    now=datetime.now(timezone.utc).date()
    params={"q":"뒷계","since":str(now-timedelta(days=30)),
            "until":str(now+timedelta(days=1))}
    assert client.get("/api/public-search-verified",params={**params,"q":"spam"}).status_code==400
    assert client.get("/api/public-search-verified",params={**params,
                "since":str(now-timedelta(days=100))}).status_code==400
    assert client.get("/api/public-search-verified",params={**params,
                "until":"2099-01-01"}).status_code==400


def test_production_runtime_packages_the_verifier():
    root=Path(__file__).resolve().parent
    docker=(root/"Dockerfile").read_text(encoding="utf-8")
    gateway=(root/"gateway.py").read_text(encoding="utf-8")
    script=(root/"bsky_search_fallback.js").read_text(encoding="utf-8")
    assert "COPY apps/demand-research/public_search_verified.py /app/public_search_verified.py" in docker
    assert "app.include_router(public_search_verified_router)" in gateway
    assert "/api/public-search-verified" in script
