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
    assert "공개 게시글" in page.text and "소비조사" in page.text


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
