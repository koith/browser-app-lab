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
