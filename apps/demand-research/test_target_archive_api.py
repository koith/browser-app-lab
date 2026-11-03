"""Private gateway-selected archive request: never makes a network request."""
import pytest
from fastapi.testclient import TestClient
import gateway
import target_archive_api


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","synthetic-private-gateway-token-that-is-long-enough")
    monkeypatch.setattr(gateway,"COOKIE","synthetic-cloud-cookie")
    monkeypatch.setenv("DEMAND_ARCHIVE_DISPATCH_TOKEN","synthetic-private-actions-writer-token")
    monkeypatch.setenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    monkeypatch.setattr(target_archive_api,"_last_request",None)
    client=TestClient(gateway.app,base_url="https://testserver")
    response=client.post("/api/activate",json={
        "token":"synthetic-private-gateway-token-that-is-long-enough"})
    assert response.status_code==200
    return client


def test_requires_authenticated_session_and_actions_permission(monkeypatch):
    test=TestClient(gateway.app,base_url="https://testserver")
    assert test.get("/api/target-archive/status").status_code==503
    assert test.post("/api/target-archive/start",json={
        "platform":"bluesky","account":"public-test.bsky.social"}).status_code==503
    monkeypatch.setattr(gateway,"TOKEN","synthetic-private-gateway-token-that-is-long-enough")
    monkeypatch.setattr(gateway,"COOKIE","synthetic-cloud-cookie")
    assert test.get("/api/target-archive/status").status_code==401


def test_archive_dispatch_fails_without_same_origin_intent(client,monkeypatch):
    invoked=[]
    monkeypatch.setattr(target_archive_api,"dispatch",lambda p,a:invoked.append((p,a)))
    body={"platform":"bluesky","account":"public-test.bsky.social"}
    assert client.post("/api/target-archive/start",json=body).status_code==403
    assert client.post("/api/target-archive/start",json=body,headers={
        "Origin":"https://untrusted.example",
        "X-Archive-Intent":"selected-public-account-v1"}).status_code==403
    assert invoked==[]


def test_authenticated_public_account_dispatch_returns_queued_not_saved(client,monkeypatch):
    invoked=[]
    monkeypatch.setattr(target_archive_api,"dispatch",lambda p,a:invoked.append((p,a)))
    headers={"Origin":"https://testserver",
             "X-Archive-Intent":"selected-public-account-v1"}
    r=client.post("/api/target-archive/start",json={
        "platform":"bluesky","account":"public-test.bsky.social"},headers=headers)
    assert r.status_code==202
    assert r.json()["state"]=="QUEUED_NOT_VERIFIED"
    assert r.json()["completion_guaranteed"] is False
    assert invoked==[("bluesky","public-test.bsky.social")]
    assert client.post("/api/target-archive/start",json={
        "platform":"bluesky","account":"public-test.bsky.social"},headers=headers).status_code==429


def test_rejects_unapproved_platform_and_private_host(client,monkeypatch):
    monkeypatch.setattr(target_archive_api,"dispatch",lambda *_:pytest.fail("not permitted"))
    headers={"Origin":"https://testserver",
             "X-Archive-Intent":"selected-public-account-v1"}
    for selection in [{"platform":"x","account":"unknown"},
                      {"platform":"mastodon","account":"user@localhost"},
                      {"platform":"bluesky","account":"https://127.0.0.1/profile/test"}]:
        assert client.post("/api/target-archive/start",json=selection,
                           headers=headers).status_code==400


def test_dispatch_missing_private_token_is_explicit_unavailable(client,monkeypatch):
    monkeypatch.delenv("DEMAND_ARCHIVE_DISPATCH_TOKEN")
    s=client.get("/api/target-archive/status")
    assert s.status_code==200 and s.json()["enabled"] is False
    assert client.post("/api/target-archive/start",
          json={"platform":"bluesky","account":"public-test.bsky.social"},
          headers={"Origin":"https://testserver",
                   "X-Archive-Intent":"selected-public-account-v1"}).status_code==503
