"""Synthetic-only contract tests. No collected social data is included."""
import os
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import gateway
from social_sources import normalize_item, parse_response, https_url, request_one_page

START=datetime(2026,10,1,tzinfo=timezone.utc)
END=datetime(2026,11,3,tzinfo=timezone.utc)
HOSTS={
    "x":"https://x.com/fixture/status/1234567890123456",
    "threads":"https://www.threads.com/@fixture/post/AB123",
    "instagram":"https://www.instagram.com/reel/TESTpost/",
    "reddit":"https://www.reddit.com/r/fixture/comments/abcdef/mock/",
}
def synthetic(platform):
    return {"post":{"id":"synthetic-001","url":HOSTS[platform],
          "published_at":"2026-11-01T09:00:00+00:00",
          "author":{"username":"fixture","display_name":"Mock User"},
          "content":{"text":"섹트 synthetic fixture","media_urls":["https://images.example.com/fixture.jpg"]}}}

def test_source_normalization_all_platforms():
    for platform in HOSTS:
        row=normalize_item(synthetic(platform),platform,"섹트",START,END)
        assert row["platform"]==platform
        assert row["url"]==HOSTS[platform]
        assert row["profileUrl"].startswith("https://")
        assert len(row["media"])==1
        assert row["posted"]=="2026-11-01T09:00:00+00:00"

def test_private_external_links_and_fake_auth_are_rejected():
    assert not https_url("http://x.com/fixture/status/1234")
    assert not https_url("https://127.0.0.1/admin")
    assert not https_url("https://10.0.0.2/config")
    assert not https_url("https://localhost/a")
    assert not https_url("https://evil.com/a",("reddit.com",))
    assert normalize_item({**synthetic("x"),"post":{**synthetic("x")["post"],"url":"https://example.com/status/123"}},"x","섹트",START,END) is None
    assert normalize_item(synthetic("x"),"x","뒷계",START,END) is None

def test_schema_missing_dates_and_implicit_nonpublic_rows():
    item=synthetic("x")
    item["post"]["published_at"]="2021-01-01T09:00:00Z"
    assert normalize_item(item,"x","섹트",START,END) is None
    item["post"]["published_at"]="2026-11-01T09:00:00Z"
    item["post"]["flags"]={"private":True}
    body={"success":True,"data":{"items":[item]},"credits_used":1,"pagination":{"has_more":False}}
    assert parse_response(body,"x","섹트",START,END)["items"]==[]
    assert parse_response(body,"x","섹트",START,END)["accepted"]==0

def test_dedup_cursor_and_stats():
    a=synthetic("threads")
    result=parse_response({"success":True,"data":{"items":[a,a,a],"dropped":0},
       "credits_used":1,"pagination":{"has_more":True,"next_cursor":"opaque"}},
       "threads","섹트",START,END)
    assert result["received"]==3 and result["accepted"]==1
    assert result["next_cursor"]=="opaque" and result["has_more"] is True
    assert result["credits_used"]==1

def test_api_key_missing_never_calls_network():
    import pytest
    with pytest.raises(ValueError,match="missing_key"):
        request_one_page("","x","섹트",START,END)
    with pytest.raises(ValueError,match="invalid_query"):
        request_one_page("dummy-key-long-enough","nope","섹트",START,END)

def test_authenticated_opt_in_and_one_call_guard(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","a-real-test-only-secret-012345678900")
    monkeypatch.setattr(gateway,"COOKIE","mock-cloud-cookie")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    monkeypatch.setenv("DEMAND_SOCIAL_SEARCH_ENABLED","1")
    monkeypatch.setenv("DEMAND_SOCIALCRAWL_API_KEY","mock-socialcrawl-secret")
    monkeypatch.setenv("DEMAND_SOCIAL_MAX_DAILY_CALLS","1")
    gateway._search_cache.clear()
    gateway._search_usage.update(date="",requests=0)
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.get("/api/discovery/status").status_code==401
    assert client.get("/api/discovery",params={"platform":"x","term":"섹트","start":"2026-10-10","end":"2026-10-11"}).status_code==401
    t=client.post("/api/activate",json={"token":gateway.TOKEN})
    assert t.status_code==200
    assert client.get("/api/discovery/status").json()["enabled"] is True
    assert client.get("/api/discovery",params={"platform":"x","term":"bad","start":"2026-10-10","end":"2026-10-11"}).status_code==400
    count={"n":0}
    def fixture(*args):
        count["n"]+=1
        return {"provider":"socialcrawl","items":[normalize_item(synthetic("x"),"x","섹트",START,END)]}
    monkeypatch.setattr(gateway,"request_one_page",fixture)
    params={"platform":"x","term":"섹트","start":"2026-10-10","end":"2026-11-02"}
    first=client.get("/api/discovery",params=params)
    assert first.status_code==200,first.text
    assert len(first.json()["items"])==1
    assert client.get("/api/discovery",params=params).json()["cache"]=="gateway"
    assert count["n"]==1
    assert client.get("/api/discovery",params={**params,"platform":"reddit"}).status_code==429
