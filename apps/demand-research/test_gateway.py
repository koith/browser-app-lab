"""No network or credentials required: validate the deployed gateway contract."""
import hmac
import pytest
from fastapi.testclient import TestClient
import gateway

def test_offline_cloud_status_is_truthful():
    client=TestClient(gateway.app)
    result=client.get("/api/health")
    assert result.status_code==200
    assert result.json()["cloud"]=="terabox"
    assert result.json()["configured"] is False

def test_oidc_bridge_denies_unsigned_and_other_workflows(monkeypatch):
    import os
    client=TestClient(gateway.app,base_url="https://testserver")
    monkeypatch.setattr(gateway,"COOKIE","")
    monkeypatch.delenv("RCLONE_CONFIG_ARCHIVE_COOKIE",raising=False)
    value="private-provider-test-credential-please-never-log"
    r=client.post("/api/bridge/credential",
       json={"assertion":"not-a-jwt","credential":value})
    assert r.status_code in (403,503)
    assert gateway.COOKIE==""
    assert "private-provider-test" not in r.text
    assert "RCLONE_CONFIG_ARCHIVE_COOKIE" not in os.environ


def test_oidc_bridge_only_accepts_trusted_verified_token(monkeypatch):
    import os
    client=TestClient(gateway.app,base_url="https://testserver")
    monkeypatch.setattr(gateway,"COOKIE","")
    monkeypatch.setattr(gateway,"TOKEN","synthetic-private-link-"+"z"*32)
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    assert client.get("/api/session").status_code==503
    observed=[]
    def trusted(assertion):
        observed.append(assertion)
        if assertion!="synthetic-verified-oidc":
            raise ValueError("Wrong workflow")
        return {"repository_id":"1284121913","ref":"refs/heads/main"}
    monkeypatch.setattr(gateway,"verify_bridge_token",trusted)
    credential="synthetic-private-terabox-cookie-test"
    rejected=client.post("/api/bridge/credential",
       json={"assertion":"malicious-other-workflow","credential":credential})
    assert rejected.status_code==403
    assert gateway.COOKIE==""
    accepted=client.post("/api/bridge/credential",
       json={"assertion":"synthetic-verified-oidc","credential":credential})
    assert accepted.status_code==200
    assert accepted.json()=={"accepted":True,"storage_configured":True}
    assert gateway.COOKIE==credential
    assert os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]==credential
    assert "synthetic-private-terabox-cookie" not in accepted.text
    assert client.get("/api/session").status_code==401
    assert observed==["malicious-other-workflow","synthetic-verified-oidc"]


def test_single_zip_remote_verification_requires_oidc_and_does_not_identify_account(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","synthetic-private-key-"+"k"*32)
    monkeypatch.setattr(gateway,"COOKIE","synthetic-remote-credential")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    monkeypatch.setattr(gateway,"verify_bridge_token",
        lambda token: {"sub":"trusted-job"} if token=="verified-synthetic" else
        (_ for _ in ()).throw(ValueError("Invalid assertion")))
    monkeypatch.setattr(gateway,"_verify_latest_account_zip",
                        lambda:{"state":"SHA_VERIFIED","posts":6,"objects":42})
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.get("/api/bridge/verify-one").status_code==403
    assert client.get("/api/bridge/verify-one",
        headers={"Authorization":"Bearer forged"}).status_code==403
    result=client.get("/api/bridge/verify-one",
        headers={"Authorization":"Bearer verified-synthetic"})
    assert result.status_code==200
    assert result.json()=={"state":"SHA_VERIFIED","posts":6,"objects":42}
    assert "synthetic-remote-credential" not in result.text


def test_archive_inventory_is_private_and_distinguishes_missing_from_verified(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","synthetic-owner-link-"+"z"*32)
    monkeypatch.setattr(gateway,"COOKIE","synthetic-terabox-fixture")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    monkeypatch.setattr(gateway,"_archive_probe",{"at":0.0,"value":None})
    calls=[]
    expected={"automated_posts":3,"account_zip_candidates":1,
              "account_zip_read_verified":1,"account_registry_count":0,
              "automated_posts_state":"ok",
              "account_bundles_state":"one_verified","account_registry_state":"ok"}
    monkeypatch.setattr(gateway,"_archive_inventory",
                        lambda:(calls.append(1) or expected))
    monkeypatch.setattr(gateway,"verify_bridge_token",
                        lambda value: {"repository":"koith/browser-app-lab"}
                        if value=="synthetic-signed-oidc" else (_ for _ in ()).throw(ValueError()))
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.get("/api/archive-overview").status_code==401
    assert client.get("/api/bridge/diagnostics").status_code==403
    assert client.get("/api/bridge/diagnostics",
        headers={"Authorization":"Bearer forged"}).status_code==403
    bridge=client.get("/api/bridge/diagnostics",
        headers={"Authorization":"Bearer synthetic-signed-oidc"})
    assert bridge.status_code==200 and bridge.json()==expected
    assert "synthetic-terabox" not in bridge.text
    assert client.post("/api/activate",
        json={"token":"synthetic-owner-link-"+"z"*32}).status_code==200
    result=client.get("/api/archive-overview")
    assert result.status_code==200 and result.json()==expected
    assert calls==[1],"private diagnostic cache should avoid duplicate cloud reads"


def test_public_readiness_requires_all_private_settings(monkeypatch):
    client=TestClient(gateway.app,base_url="https://testserver")
    monkeypatch.delenv("DEMAND_ARCHIVE_DISPATCH_TOKEN",raising=False)
    monkeypatch.setattr(gateway,"TOKEN","synthetic-private-viewer-secret-"+"x"*32)
    monkeypatch.setattr(gateway,"COOKIE","synthetic-terabox-credential")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    # The Render service can be alive but not ready for one-click backups.
    assert client.get("/health").json()=={"alive":True}
    pending=client.get("/ready",headers={"Origin":"https://koith.github.io"})
    assert pending.status_code==503 and pending.json()=={"ready":False}
    assert pending.headers["cache-control"]=="no-store"
    monkeypatch.setenv("DEMAND_ARCHIVE_DISPATCH_TOKEN","synthetic-actions-secret-"+"y"*32)
    ready=client.get("/ready",headers={"Origin":"https://koith.github.io"})
    assert ready.status_code==200 and ready.json()=={"ready":True}
    assert ready.headers["access-control-allow-origin"]=="https://koith.github.io"
    assert "synthetic" not in ready.text
    monkeypatch.setattr(gateway,"COOKIE","")
    assert client.get("/ready").status_code==503


def test_private_catalog_fails_closed_without_credentials():
    assert TestClient(gateway.app).get("/api/posts").status_code==503

def test_valid_empty_catalog():
    assert gateway.validate_catalog({"schema_version":1,"posts":[]})==[]

@pytest.mark.parametrize("bad",[
    {},[],{"schema_version":2,"posts":[]},
    {"schema_version":1,"posts":{}},
    {"schema_version":1,"posts":[{"id":"bad","text":"test","media":[]}]},
])
def test_bad_catalog_rejected(bad):
    with pytest.raises(ValueError):
        gateway.validate_catalog(bad)

def test_valid_media_and_bad_path():
    m={"key":"posts/0123456789abcdef/media/0001.jpg","mime":"image/jpeg","bytes":11,
       "sha256":"c"*64,"remote_verified":True}
    p={"id":"0123456789abcdef","text":"approved test","media":[m]}
    data={"schema_version":1,"posts":[p]}
    assert gateway.validate_catalog(data)==[p]
    m["key"]="posts/0123456789abcdef/media/../../secrets"
    with pytest.raises(ValueError):gateway.validate_catalog(data)

def test_unverified_blob_rejected():
    m={"key":"posts/0123456789abcdef/media/0001.jpg","mime":"image/jpeg","bytes":11,
       "sha256":"c"*64,"remote_verified":False}
    with pytest.raises(ValueError):
        gateway.validate_catalog({"schema_version":1,"posts":[{"id":"0123456789abcdef","text":"test","media":[m]}]})

def test_signature_covers_post_index_and_expiry(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","z"*32)
    a=gateway.media_signature("0123456789abcdef",0,100)
    assert hmac.compare_digest(a,gateway.media_signature("0123456789abcdef",0,100))
    assert a!=gateway.media_signature("0123456789abcdef",1,100)
    assert a!=gateway.media_signature("0123456789abcdef",0,101)

def test_signed_media_does_not_work_offline():
    assert TestClient(gateway.app).get("/api/media/0123456789abcdef/0?exp=1000&sig=bad").status_code==503


@pytest.fixture
def connected_gateway(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","strong-secret-link-only-for-local-tests-012345")
    monkeypatch.setattr(gateway,"COOKIE","fake-authorized-terabox-session")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    return TestClient(gateway.app,base_url="https://testserver")


def test_url_only_mode_does_not_require_login_for_public_apis(connected_gateway,monkeypatch):
    monkeypatch.setenv("DEMAND_PUBLIC_ARCHIVE_MODE","1")
    assert connected_gateway.get("/api/session").status_code==200
    assert connected_gateway.get("/api/target-archive/status").status_code==200
    assert connected_gateway.post("/api/accounts/sync").status_code==401


def test_public_bluesky_asset_is_served_without_repeated_404():
    client=TestClient(gateway.app,base_url="https://testserver")
    response=client.get("/assets/bluesky.svg")
    assert response.status_code==200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in response.content
    assert client.get("/assets/private.svg").status_code==404


def test_home_has_no_login_or_password(connected_gateway):
    page=connected_gateway.get("/")
    assert page.status_code==200
    assert "text/html" in page.headers["content-type"]
    assert page.headers["referrer-policy"]=="no-referrer"
    assert "noindex" in page.headers["x-robots-tag"]
    assert 'type="password"' not in page.text
    assert 'id="login"' not in page.text
    assert "INTERSECTION" in page.text and "공개 게시글" in page.text


def test_one_click_activation_cookie_and_auto_session(connected_gateway):
    client=connected_gateway
    assert client.get("/api/session").status_code==401
    assert client.get("/api/posts").status_code==401
    bad=client.post("/api/activate",json={"token":"wrong"})
    assert bad.status_code==403
    good=client.post("/api/activate",
        json={"token":"strong-secret-link-only-for-local-tests-012345"})
    assert good.status_code==200
    cookie=good.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert "demand_view" in cookie
    assert client.get("/api/session").status_code==200


def test_wrong_and_oversized_activation_payload(connected_gateway):
    client=connected_gateway
    assert client.post("/api/activate",data="not json").status_code==400
    assert client.post("/api/activate",data="x"*600).status_code==413
    assert client.post("/api/activate",json=["not an object"]).status_code==400


def test_link_rotation_revokes_session(connected_gateway,monkeypatch):
    client=connected_gateway
    token="strong-secret-link-only-for-local-tests-012345"
    assert client.post("/api/activate",json={"token":token}).status_code==200
    assert client.get("/api/session").status_code==200
    monkeypatch.setattr(gateway,"TOKEN","rotated-secret-link-only-for-local-tests-987654")
    assert client.get("/api/session").status_code==401


def test_existing_post_card_api_uses_cookie_not_password(connected_gateway,monkeypatch):
    async def fake_catalog():
        return [{"id":"0123456789abcdef","platform":"bluesky",
                 "posted_at":"2026-11-01T00:00:00Z","text":"Test authorized sample",
                 "media":[{"key":"posts/0123456789abcdef/media/a.jpg",
                           "mime":"image/jpeg","bytes":10,
                           "sha256":"c"*64,"remote_verified":True}]}]
    monkeypatch.setattr(gateway,"get_catalog",fake_catalog)
    client=connected_gateway
    assert client.post("/api/activate",json={
        "token":"strong-secret-link-only-for-local-tests-012345"}).status_code==200
    r=client.get("/api/posts")
    assert r.status_code==200
    assert r.json()["total"]==1
    p=r.json()["posts"][0]
    assert p["text"]=="Test authorized sample"
    assert len(p["media"])==1
    assert p["media"][0]["url"].startswith("/api/media/0123456789abcdef/0?exp=")


def test_logout_without_password_prompt(connected_gateway):
    client=connected_gateway
    assert client.post("/api/activate",json={
        "token":"strong-secret-link-only-for-local-tests-012345"}).status_code==200
    assert client.post("/api/end-session").status_code==200
    assert client.get("/api/session").status_code==401


def test_private_archive_query_filters_all_remote_rows(connected_gateway,monkeypatch):
    """Search/filter on the server before paging; never silently hide partials."""
    import time
    client=connected_gateway
    pbase={"posted_at":"2026-11-03T00:00:00Z","text":"synthetic coffee purchase",
           "media":[],"media_expected":0,"archive_complete":True}
    async def catalog():
        return [
            {**pbase,"id":"a"*40,"platform":"bluesky"},
            {**pbase,"id":"b"*40,"platform":"mastodon","text":"synthetic train experience",
             "media_expected":2,"archive_complete":False},
        ]
    monkeypatch.setattr(gateway,"get_catalog",catalog)
    assert client.post("/api/activate",json={"token":"strong-secret-link-only-for-local-tests-012345"}).status_code==200
    all_rows=client.get("/api/posts").json()
    assert all_rows["total"]==2
    assert client.get("/api/posts?q=coffee").json()["total"]==1
    assert client.get("/api/posts?platform=mastodon").json()["total"]==1
    incomplete=client.get("/api/posts?media_status=partial").json()
    assert incomplete["total"]==1
    assert incomplete["posts"][0]["media_expected"]==2
    assert incomplete["posts"][0]["media_saved"]==0
    assert client.get("/api/posts?media_status=complete").json()["total"]==1
    assert client.get("/api/posts?platform=invalid").status_code==400
    assert client.get("/api/posts?media_status=unknown").status_code==400


def test_auto_viewer_requires_auth(connected_gateway):
    client=connected_gateway
    assert client.get("/auto-archive").status_code==401
    assert client.get("/auto-archive/auto_archive_view.js").status_code==401
    assert client.get("/auto-archive/auto_archive_view.css").status_code==401


def test_auto_viewer_read_only_assets(connected_gateway):
    client=connected_gateway
    token=gateway.TOKEN
    assert client.post("/api/activate",json={"token":token}).status_code==200
    page=client.get("/auto-archive")
    assert page.status_code==200
    assert "frame-ancestors 'self'" in page.headers["content-security-policy"]
    assert "no-store" in page.headers["cache-control"]
    for asset in ("auto_archive_view.js","auto_archive_view.css"):
        assert client.get("/auto-archive/"+asset).status_code==200
    assert client.get("/auto-archive/gateway.py").status_code==404


def test_auto_viewer_serves_origin_locked_original_browser_code(connected_gateway):
    client=connected_gateway
    client.post("/api/activate",json={"token":"strong-secret-link-only-for-local-tests-012345"})
    page=client.get("/auto-archive")
    assert page.status_code==200
    assert "frame-ancestors 'self'" in page.headers["content-security-policy"]
    assert "frame-ancestors 'none'" not in page.headers["content-security-policy"]
    assert "자동 수집 원본" in page.text
    assert client.get("/auto-archive/auto_archive_view.js").status_code==200
    assert client.get("/auto-archive/auto_archive_view.css").status_code==200
    assert client.get("/auto-archive/gateway.py").status_code==404


def test_original_media_verified_against_real_bytes_not_metadata_only(
        connected_gateway,monkeypatch):
    import hashlib
    from urllib.parse import urlsplit,parse_qs
    blob=b"synthetic-public-original-video-content"
    pid="a"*40
    original_hash=hashlib.sha256(blob).hexdigest()
    post={"id":pid,"platform":"bluesky","posted_at":"2026-11-01T00:00:00Z",
          "text":"synthetic public keyword post","archive_complete":True,
          "media":[{"key":"posts/"+pid+"/media/0001.mp4",
                    "mime":"video/mp4","bytes":len(blob),
                    "sha256":original_hash,"remote_verified":True,"kind":"video"}]}
    async def catalog():return [post]
    monkeypatch.setattr(gateway,"get_catalog",catalog)
    calls=[]
    class FakeArchive:
        def __init__(self,*args,**kwargs):pass
        def read_verified(self,key,digest,*,cap):
            calls.append((key,digest,cap))
            return blob if not calls_or_corrupt["fail"] else b"tampered-original-video"
    calls_or_corrupt={"fail":False}
    monkeypatch.setattr(gateway,"CloudArchive",FakeArchive)
    client=connected_gateway
    client.post("/api/activate",json={"token":"strong-secret-link-only-for-local-tests-012345"})
    post_result=client.get("/api/posts").json()["posts"][0]
    path=post_result["media"][0]["url"]
    r=client.get(path)
    assert r.status_code==200
    assert r.content==blob
    assert calls[0]==(post["media"][0]["key"],original_hash,len(blob)+1)
    r=client.get(path,headers={"Range":"bytes=4-13"})
    assert r.status_code==206 and r.content==blob[4:14]
    assert r.headers["content-range"]=="bytes 4-13/"+str(len(blob))
    calls_or_corrupt["fail"]=True
    assert client.get(path).status_code==502


def test_media_must_be_sha_readable_even_if_url_is_signed(connected_gateway,monkeypatch):
    import hashlib
    pid="b"*40
    blob=b"synthetic-image-content"
    async def catalog():
        return [{"id":pid,"platform":"mastodon","posted_at":"2026-11-01T00:00:00Z",
                 "text":"synthetic public","media":[{
                   "key":"posts/"+pid+"/media/0001.png",
                   "mime":"image/png","bytes":len(blob),
                   "sha256":hashlib.sha256(blob).hexdigest(),"remote_verified":True
                 }]}]
    monkeypatch.setattr(gateway,"get_catalog",catalog)
    class MissingArchive:
        def __init__(self,*args,**kwargs):pass
        def read_verified(self,*args,**kwargs):return None
    monkeypatch.setattr(gateway,"CloudArchive",MissingArchive)
    client=connected_gateway
    client.post("/api/activate",json={"token":"strong-secret-link-only-for-local-tests-012345"})
    url=client.get("/api/posts").json()["posts"][0]["media"][0]["url"]
    assert client.get(url).status_code==502


def test_archive_key_oidc_authorizes_only_exact_main_account_or_mirror_workflow(monkeypatch):
    import base64
    import github_temp_bundle
    client=TestClient(gateway.app,base_url="https://testserver")
    monkeypatch.setattr(github_temp_bundle,"gateway_key",lambda:b"k"*32)
    monkeypatch.setattr(gateway,"COOKIE","")
    observed=[]
    def signed(token,workflow=gateway.BRIDGE_WORKFLOW):
        observed.append((token,workflow))
        allowed={
            "signed-account":gateway.ARCHIVE_WORKFLOW,
            "signed-zip-mirror":gateway.MIRROR_WORKFLOW,
        }
        if allowed.get(token)!=workflow:
            raise ValueError("unapproved subject")
        return {"workflow_ref":workflow,"ref":"refs/heads/main"}
    monkeypatch.setattr(gateway,"verify_bridge_token",signed)
    for token in ("signed-account","signed-zip-mirror"):
        result=client.get("/api/bridge/archive-key",headers={
            "Authorization":"Bearer "+token})
        assert result.status_code==200,result.status_code
        assert base64.b64decode(result.json()["key"])==b"k"*32
        assert "synthetic" not in result.text
    for token in ("unrelated-action","signed-other-ref",""):
        response=client.get("/api/bridge/archive-key",headers={
            "Authorization":"Bearer "+token})
        assert response.status_code==403
    # The new mirror is allowed to receive only the encryption key;
    # it must never update Render's provider credential.
    bad=client.post("/api/bridge/credential",json={
        "assertion":"signed-zip-mirror",
        "credential":"synthetic-credential-should-stay-rejected"})
    assert bad.status_code==403
    assert gateway.COOKIE==""
    assert any(workflow==gateway.MIRROR_WORKFLOW for _,workflow in observed)



def test_account_status_background_refresh_is_singleflight_and_cooled_down(monkeypatch):
    import asyncio
    calls=[]
    async def fake_refresh():
        calls.append("refresh")
        await asyncio.sleep(0)

    async def exercise():
        monkeypatch.setattr(gateway,"_index_task",None)
        monkeypatch.setattr(gateway,"_index_lazy_task",None)
        monkeypatch.setattr(gateway,"_index_lazy_attempt_at",0.0)
        monkeypatch.setattr(gateway,"_index_synced_at",0.0)
        monkeypatch.setattr(gateway,"_index_lock",asyncio.Lock())
        monkeypatch.setattr(gateway,"_background_account_index_refresh",fake_refresh)
        assert gateway.schedule_lazy_account_index_refresh() is True
        assert gateway.schedule_lazy_account_index_refresh() is False
        await gateway._index_lazy_task
        assert calls == ["refresh"]
        # Even when a failed index leaves no successful checkpoint, a burst
        # of page refreshes must not schedule another expensive cloud read.
        assert gateway.schedule_lazy_account_index_refresh() is False

        class RunningPeriodic:
            def done(self):
                return False
        monkeypatch.setattr(gateway,"_index_lazy_attempt_at",0.0)
        monkeypatch.setattr(gateway,"_index_task",RunningPeriodic())
        assert gateway.schedule_lazy_account_index_refresh() is False
        assert calls == ["refresh"]

    asyncio.run(exercise())



def test_remote_account_index_snapshot_sha_checked_then_hydrated(tmp_path,monkeypatch):
    import shutil
    import account_index
    import account_index_job
    src=tmp_path/"verified_source.sqlite3"
    target=tmp_path/"gateway.sqlite3"
    account_index.sync_catalog(str(src),[{
        "id":"synthetic-post","platform":"x",
        "profile_url":"https://x.com/testsyn",
        "text":"synthetic index only"}])
    assert account_index.status(str(src))["accounts"]==1
    monkeypatch.setattr(gateway,"INDEX_DB",str(target))
    expected={"file":"snapshot-123456789.sqlite3",
              "sha256":"b"*64,"catalog":"deferred_timeout"}
    calls=[]
    monkeypatch.setattr(account_index_job,"latest_manifest",lambda:expected)
    def sha_verified_reader(path,manifest):
        calls.append(manifest["sha256"])
        shutil.copyfile(src,path)
    monkeypatch.setattr(account_index_job,"load_snapshot",sha_verified_reader)
    result=gateway._read_verified_account_index_snapshot()
    assert result["accounts"]==1
    assert result["catalog"]=="deferred_timeout"
    assert result["unchanged"] is False
    assert account_index.status(str(target))["accounts"]==1
    assert gateway._read_verified_account_index_snapshot(expected["sha256"])["unchanged"] is True
    assert calls==[expected["sha256"]]


def test_unverified_remote_index_download_cannot_clobber_live_db(tmp_path,monkeypatch):
    import account_index
    import account_index_job
    target=tmp_path/"gateway.sqlite3"
    account_index.sync_catalog(str(target),[{
        "id":"old-synthetic","platform":"x",
        "profile_url":"https://x.com/verifyold",
        "text":"Existing data must survive"}])
    monkeypatch.setattr(gateway,"INDEX_DB",str(target))
    monkeypatch.setattr(account_index_job,"latest_manifest",lambda:{
        "file":"snapshot-123456790.sqlite3","sha256":"a"*64})
    def unreadable(_path,_manifest):
        raise RuntimeError("simulated checksum failure")
    monkeypatch.setattr(account_index_job,"load_snapshot",unreadable)
    with pytest.raises(RuntimeError,match="checksum"):
        gateway._read_verified_account_index_snapshot()
    assert account_index.status(str(target))["accounts"]==1


def test_account_snapshot_refresh_metadata_only_after_success(monkeypatch):
    import asyncio
    calls=[]
    monkeypatch.setattr(gateway,"INDEX_DB","fixture-not-used.sqlite3")
    monkeypatch.setattr(gateway,"_index_snapshot_info",
                        {"sha256":"","catalog":"not_checked","verified":False})
    monkeypatch.setattr(gateway,"_index_synced_at",0.0)
    monkeypatch.setattr(gateway,"_index_lock",asyncio.Lock())
    monkeypatch.setattr(gateway,"_read_verified_account_index_snapshot",
        lambda known:(calls.append(known) or {
            "sha256":"c"*64,"catalog":"deferred_timeout","unchanged":False,
            "accounts":2,"source_rows":6}))
    asyncio.run(gateway.refresh_account_index())
    assert calls==[""]
    assert gateway._index_snapshot_info["verified"] is True
    assert gateway._index_snapshot_info["catalog"]=="deferred_timeout"



def test_oidc_signed_snapshot_import_is_sha_checked_idempotent_and_monotonic(tmp_path,monkeypatch):
    import hashlib
    import sqlite3
    import account_index
    candidate=tmp_path/"verified.sqlite3"
    viewer=tmp_path/"viewer.sqlite3"
    account_index.sync_catalog(str(candidate),[{
        "id":"synthetic-original","platform":"x",
        "profile_url":"https://x.com/qa_test_a",
        "text":"synthetic public index test"}])
    with sqlite3.connect(str(candidate)) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    blob=candidate.read_bytes()
    digest=hashlib.sha256(blob).hexdigest()
    monkeypatch.setattr(gateway,"INDEX_DB",str(viewer))
    monkeypatch.setattr(gateway,"_index_snapshot_info",
                        {"sha256":"","catalog":"not_checked","verified":False})
    def trusted(token,workflow=gateway.BRIDGE_WORKFLOW):
        if token!="synthetic-main-oidc" or workflow!=gateway.INDEX_IMPORT_WORKFLOW:
            raise ValueError("wrong main workflow")
        return {"repository":"koith/browser-app-lab","ref":"refs/heads/main"}
    monkeypatch.setattr(gateway,"verify_bridge_token",trusted)
    client=TestClient(gateway.app)
    headers={"Authorization":"Bearer synthetic-main-oidc",
             "X-Index-SHA256":digest,"X-Index-Source-Run":"42445680007"}
    assert client.post("/api/bridge/index-snapshot",content=blob).status_code==403
    denied=client.post("/api/bridge/index-snapshot",
                       content=blob,headers={**headers,"Authorization":"Bearer another-workflow"})
    assert denied.status_code==403
    assert account_index.status(str(viewer))["accounts"]==0
    invalid=client.post("/api/bridge/index-snapshot",
                        content=blob,headers={**headers,"X-Index-SHA256":"0"*64})
    assert invalid.status_code==422
    assert account_index.status(str(viewer))["accounts"]==0
    accepted=client.post("/api/bridge/index-snapshot",content=blob,headers=headers)
    assert accepted.status_code==200, accepted.text
    assert accepted.json()["accepted"] is True
    assert accepted.json()["accounts"]==1
    assert account_index.status(str(viewer))["accounts"]==1
    assert gateway._index_snapshot_info["verified"] is True
    assert client.post("/api/bridge/index-snapshot",content=blob,headers=headers).status_code==200
    stale=client.post("/api/bridge/index-snapshot",content=blob,
                      headers={**headers,"X-Index-Source-Run":"42445679999"})
    assert stale.status_code==409
    assert account_index.status(str(viewer))["accounts"]==1


def test_oidc_signed_snapshot_rejects_corrupted_sqlite_without_clobber(tmp_path,monkeypatch):
    import hashlib
    import account_index
    viewer=tmp_path/"index.sqlite3"
    account_index.sync_catalog(str(viewer),[{
        "id":"existing-fixture","platform":"x",
        "profile_url":"https://x.com/qa_test_b",
        "text":"Do not erase existing checked rows"}])
    monkeypatch.setattr(gateway,"INDEX_DB",str(viewer))
    monkeypatch.setattr(gateway,"verify_bridge_token",
                        lambda token,workflow=None: {"repository":"koith/browser-app-lab"})
    blob=b"not a SQLite snapshot"
    client=TestClient(gateway.app)
    r=client.post("/api/bridge/index-snapshot",content=blob,headers={
        "Authorization":"Bearer synthetic-test","X-Index-SHA256":hashlib.sha256(blob).hexdigest(),
        "X-Index-Source-Run":"42445680008"})
    assert r.status_code==422
    assert account_index.status(str(viewer))["accounts"]==1
    assert "qa_test_b" not in r.text


def test_verified_signed_index_receipt_recovers_after_process_restart(tmp_path,monkeypatch):
    import account_index
    path=tmp_path/"persisted.sqlite3"
    account_index.sync_catalog(str(path),[{
        "id":"synthetic-restart-1","platform":"x",
        "profile_url":"https://x.com/qa_probe",
        "text":"synthetic public row"}])
    with account_index.connect(str(path)) as db:
        db.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                   ("last_imported_index_run","42547929782"))
        db.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                   ("last_imported_index_sha","a"*64))
        db.commit()
    assert gateway.verified_signed_import_receipt(str(path)) is True
    monkeypatch.setattr(gateway,"INDEX_DB",str(path))
    monkeypatch.setattr(gateway,"_index_snapshot_info",
                        {"sha256":"","catalog":"not_checked","verified":False})
    monkeypatch.setattr(gateway,"check_auth",lambda request:None)
    monkeypatch.setattr(gateway,"schedule_lazy_account_index_refresh",lambda:False)
    monkeypatch.setenv("DEMAND_AUTO_PUBLIC_INDEX","0")
    r=TestClient(gateway.app).get("/api/accounts/status")
    assert r.status_code==200
    assert r.json()["accounts"]==1
    assert r.json()["remote_snapshot_verified"] is True
    assert r.json()["remote_catalog_state"]=="not_verified"


def test_signed_index_receipt_rejects_unverified_or_corrupt_state(tmp_path):
    import account_index
    path=tmp_path/"unverified.sqlite3"
    account_index.sync_catalog(str(path),[{
        "id":"synthetic-restart-2","platform":"x",
        "profile_url":"https://x.com/qa_probe",
        "text":"synthetic unverified row"}])
    assert gateway.verified_signed_import_receipt(str(path)) is False
    with account_index.connect(str(path)) as db:
        db.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                   ("last_imported_index_run","42547929782"))
        db.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                   ("last_imported_index_sha","not-a-valid-sha"))
        db.commit()
    assert gateway.verified_signed_import_receipt(str(path)) is False
    assert gateway.verified_signed_import_receipt(str(tmp_path/"missing.db")) is False
    invalid=tmp_path/"corrupt.db"
    invalid.write_bytes(b"not-sqlite")
    assert gateway.verified_signed_import_receipt(str(invalid)) is False



def test_exact_main_index_delivery_can_obtain_derived_boot_cipher_key(monkeypatch):
    import base64
    import github_temp_bundle
    seen=[]
    def verified_oidc(token,workflow=None):
        seen.append(workflow)
        if token!="synthetic-main-index" or workflow!=gateway.INDEX_IMPORT_WORKFLOW:
            raise ValueError("not this exact workflow")
        return {"repository":"koith/browser-app-lab","ref":"refs/heads/main"}
    monkeypatch.setattr(gateway,"verify_bridge_token",verified_oidc)
    monkeypatch.setattr(github_temp_bundle,"gateway_key",lambda:b"k"*32)
    client=TestClient(gateway.app)
    denied=client.get("/api/bridge/archive-key",
                      headers={"Authorization":"Bearer untrusted-index"})
    assert denied.status_code==403
    assert "key" not in denied.text
    accepted=client.get("/api/bridge/archive-key",
                        headers={"Authorization":"Bearer synthetic-main-index"})
    assert accepted.status_code==200
    assert base64.b64decode(accepted.json()["key"],validate=True)==b"k"*32
    assert gateway.INDEX_IMPORT_WORKFLOW in seen


def test_archive_overview_default_does_not_spawn_full_terabox_inventory(monkeypatch):
    """A read-only tab opening must not start a large rclone listing on 512MiB."""
    monkeypatch.delenv("DEMAND_ARCHIVE_OVERVIEW_REMOTE_LIST",raising=False)
    def forbidden_cloud(*args,**kwargs):
        raise AssertionError("passive archive tab must not open TeraBox root")
    monkeypatch.setattr(gateway,"CloudArchive",forbidden_cloud)
    details=gateway._archive_inventory()
    assert details["account_bundles_state"]=="listing_deferred_memory_guard"
    assert details["post_journal_state"]=="listing_deferred_memory_guard"
    assert details["account_zip_read_verified"] is None


def test_low_memory_render_skips_background_remote_index_refresh(monkeypatch):
    """An idle page status call must not launch remote scanning on a 512MiB app."""
    import asyncio
    monkeypatch.setenv("DEMAND_ACCOUNT_INDEX_REMOTE_POLL","0")
    monkeypatch.setattr(gateway,"_index_task",None)
    monkeypatch.setattr(gateway,"_index_lazy_task",None)
    monkeypatch.setattr(gateway,"_index_lazy_attempt_at",0.0)
    monkeypatch.setattr(gateway,"_index_synced_at",0.0)
    monkeypatch.setattr(asyncio,"create_task",
        lambda *args,**kwargs: (_ for _ in ()).throw(
            AssertionError("automatic network scan must not be created")))
    assert gateway.remote_index_poll_enabled() is False
    assert gateway.schedule_lazy_account_index_refresh() is False


def test_index_poll_feature_flag_retains_default_for_non_render(monkeypatch):
    monkeypatch.delenv("DEMAND_ACCOUNT_INDEX_REMOTE_POLL",raising=False)
    assert gateway.remote_index_poll_enabled() is True
    monkeypatch.setenv("DEMAND_ACCOUNT_INDEX_REMOTE_POLL","1")
    assert gateway.remote_index_poll_enabled() is True
