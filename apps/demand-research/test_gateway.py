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
