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


def test_public_backup_start_and_poll_without_admin_cookie(monkeypatch):
    # Regression: the public browser previously received 502 AFTER the
    # TeraBox queue accepted a job, because make_receipt demanded a login
    # cookie. Then /jobs also returned 401 despite public site mode.
    monkeypatch.setenv("DEMAND_PUBLIC_ARCHIVE_MODE","1")
    monkeypatch.delenv("DEMAND_ARCHIVE_QUEUE_MODE",raising=False)
    monkeypatch.setenv("DEMAND_ARCHIVE_DISPATCH_TOKEN",
                       "synthetic-actions-token-"+"z"*32)
    monkeypatch.setenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    monkeypatch.setattr(gateway,"TOKEN","synthetic-public-server-secret-"+"x"*32)
    monkeypatch.setattr(gateway,"COOKIE","synthetic-public-source-cookie")
    monkeypatch.setattr(target_archive_api,"_last_request",None)
    calls=[]
    monkeypatch.setattr(target_archive_api,"dispatch",
                        lambda platform,account:(
                          calls.append((platform,account)) or 41999999999))
    anonymous=TestClient(gateway.app,base_url="https://testserver")
    assert not anonymous.cookies
    assert anonymous.get("/api/target-archive/status").status_code==200
    response=anonymous.post("/api/target-archive/start",
        headers={"Origin":"https://testserver",
                 "X-Archive-Intent":"selected-public-account-v1"},
        json={"platform":"bluesky","account":"@Example"})
    assert response.status_code==202,response.text
    body=response.json()
    assert body["accepted"] is True and body["state"]=="QUEUED_NOT_VERIFIED"
    assert body["run_id"]==41999999999
    assert calls==[("bluesky","example.bsky.social")]
    assert not anonymous.cookies
    monkeypatch.setattr(target_archive_api,"get_workflow_run",
        lambda run_id:{"status":"in_progress","id":run_id})
    url="/api/target-archive/jobs/"+str(body["run_id"])+"?receipt="+body["receipt"]
    result=anonymous.get(url)
    assert result.status_code==200,result.text
    assert result.json()["state"]=="RUNNING"
    assert result.json()["remote_verified"] is False
    altered=body["receipt"][:-1]+(
        "1" if body["receipt"].endswith("0") else "0")
    assert anonymous.get(url.replace(body["receipt"],altered)).status_code==403
    assert anonymous.get("/api/target-archive/jobs/41999999999?receipt=invalid").status_code==422
    assert anonymous.post("/api/target-archive/start",
        json={"platform":"bluesky","account":"@Example"}).status_code==403
    assert anonymous.post("/api/target-archive/start",
        headers={"Origin":"https://attacker.example",
                 "X-Archive-Intent":"selected-public-account-v1"},
        json={"platform":"bluesky","account":"@Example"}).status_code==403


def test_short_bluesky_username_creates_canonical_backup_request(client,monkeypatch):
    monkeypatch.delenv("DEMAND_ARCHIVE_QUEUE_MODE",raising=False)
    recorded=[]
    monkeypatch.setattr(target_archive_api,"dispatch",
                        lambda platform,account: (recorded.append((platform,account)) or 41999999999))
    headers={"Origin":"https://testserver","X-Archive-Intent":"selected-public-account-v1"}
    response=client.post("/api/target-archive/start",
                         json={"platform":"bluesky","account":"@Example"},
                         headers=headers)
    assert response.status_code==202
    assert response.json()["state"]=="QUEUED_NOT_VERIFIED"
    assert recorded==[("bluesky","example.bsky.social")]


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
    monkeypatch.setattr(target_archive_api,"dispatch",lambda p,a:(invoked.append((p,a)) or 41999999999))
    body={"platform":"bluesky","account":"public-test.bsky.social"}
    assert client.post("/api/target-archive/start",json=body).status_code==403
    assert client.post("/api/target-archive/start",json=body,headers={
        "Origin":"https://untrusted.example",
        "X-Archive-Intent":"selected-public-account-v1"}).status_code==403
    assert invoked==[]


def test_authenticated_public_account_dispatch_returns_queued_not_saved(client,monkeypatch):
    invoked=[]
    monkeypatch.setattr(target_archive_api,"dispatch",lambda p,a:(invoked.append((p,a)) or 41999999999))
    headers={"Origin":"https://testserver",
             "X-Archive-Intent":"selected-public-account-v1"}
    r=client.post("/api/target-archive/start",json={
        "platform":"bluesky","account":"public-test.bsky.social"},headers=headers)
    assert r.status_code==202
    assert r.json()["state"]=="QUEUED_NOT_VERIFIED"
    assert r.json()["completion_guaranteed"] is False
    assert r.json()["run_id"]==41999999999
    assert "." in r.json()["receipt"]
    assert "DEMAND_ARCHIVE_DISPATCH_TOKEN" not in str(r.json())
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


def test_oneclick_job_progress_requires_signed_same_session_receipt(client,monkeypatch):
    monkeypatch.setattr(target_archive_api,"dispatch",lambda *_:41999999999)
    headers={"Origin":"https://testserver","X-Archive-Intent":"selected-public-account-v1"}
    receipt=client.post("/api/target-archive/start",
        json={"platform":"bluesky","account":"public-test.bsky.social"},
        headers=headers).json()["receipt"]
    recorded=[]
    def fake_run(run_id):
        recorded.append(run_id)
        return {"status":"in_progress","id":run_id}
    monkeypatch.setattr(target_archive_api,"get_workflow_run",fake_run)
    uri="/api/target-archive/jobs/41999999999?receipt="+receipt
    response=client.get(uri)
    assert response.status_code==200
    assert response.json()["state"]=="RUNNING"
    assert response.json()["remote_verified"] is False
    assert recorded==[41999999999]
    wrong=client.get("/api/target-archive/jobs/41999999998?receipt="+receipt)
    assert wrong.status_code==403
    # Flip the final digest character to a DIFFERENT value. Replacing
    # an existing "0" with "0" would falsely report a security regression.
    altered=receipt[:-1]+("1" if receipt.endswith("0") else "0")
    assert client.get(uri.replace(receipt,altered)).status_code==403
    anon=TestClient(gateway.app,base_url="https://testserver")
    assert anon.get(uri).status_code==401


def test_finished_workflow_is_not_verification_until_remote_zip_reads_back(client,monkeypatch):
    monkeypatch.setattr(target_archive_api,"dispatch",lambda *_:41999999999)
    headers={"Origin":"https://testserver","X-Archive-Intent":"selected-public-account-v1"}
    receipt=client.post("/api/target-archive/start",
        json={"platform":"bluesky","account":"public-test.bsky.social"},
        headers=headers).json()["receipt"]
    uri="/api/target-archive/jobs/41999999999?receipt="+receipt
    run={"id":41999999999,"status":"completed","conclusion":"success"}
    monkeypatch.setattr(target_archive_api,"get_workflow_run",lambda _:run)
    monkeypatch.setattr(target_archive_api,"read_exact_verified_archive",
        lambda *args:None)
    assert client.get(uri).json()["state"]=="VERIFYING_STORAGE"
    assert client.get(uri).json()["remote_verified"] is False
    monkeypatch.setattr(target_archive_api,"read_exact_verified_archive",
        lambda *args:{"state":"REMOTE_VERIFIED","remote_verified":True,
                     "posts":6,"objects":42,
                     "account_key":"bluesky-"+"a"*40})
    passed=client.get(uri)
    assert passed.status_code==200 and passed.json()["state"]=="REMOTE_VERIFIED"
    assert passed.json()["posts"]==6 and passed.json()["objects"]==42
    run["conclusion"]="failure"
    failed=client.get(uri)
    assert failed.json()["state"]=="FAILED"
    assert failed.json()["remote_verified"] is False


def test_dispatch_requires_exact_trackable_run_id(client,monkeypatch):
    monkeypatch.setattr(target_archive_api,"_github_api",lambda *args:{
        "workflow_run_id":42001234000,"html_url":"https://github.com/owner/ignore"})
    assert target_archive_api.dispatch("bluesky","public-test.bsky.social")==42001234000
    monkeypatch.setattr(target_archive_api,"_github_api",lambda *args:{})
    with pytest.raises(RuntimeError,match="trackable"):
        target_archive_api.dispatch("bluesky","public-test.bsky.social")


def test_unrelated_workflow_never_counts_as_archived(client,monkeypatch):
    monkeypatch.setattr(target_archive_api,"_github_api",lambda *args:{
        "id":41999999999,"status":"completed","conclusion":"success",
        "path":".github/workflows/unrelated.yml","event":"workflow_dispatch",
        "head_branch":"main"})
    with pytest.raises(RuntimeError,match="does not match"):
        target_archive_api.get_workflow_run(41999999999)
