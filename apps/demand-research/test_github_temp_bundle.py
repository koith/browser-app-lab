"""Offline synthetic tests: no GitHub network, no TeraBox, no public personal data."""
import hashlib
import pytest
import github_temp_bundle as gh
from target_account_bundle import execute_bundle
from test_target_account_archive import BlueAPI, blue_row
from verified_bundle_reader import BundleAccountCloud, BundleInvalid
from target_account_viewer import feed_data


def create_synthetic_zip(monkeypatch):
    monkeypatch.delenv("DEMAND_ACCOUNT_TEMP_STORAGE", raising=False)
    api=BlueAPI({None:([blue_row("github001","Synthetic public account original")],None)})
    saved=[]
    def capture(path,*,run_id,account_hash):
        saved.append(path.read_bytes())
        return {"bytes":path.stat().st_size}
    result=execute_bundle(selected={"platform":"bluesky",
                     "account":"qa-example.bsky.social","max_pages":1},
                     api=api,run_id="42340001000",cloud_check=False,uploader=capture)
    assert result["public_posts_in_bundle"]==1
    return saved[0]


def test_temporary_bundle_encrypt_decrypt_and_manifest(monkeypatch):
    raw=create_synthetic_zip(monkeypatch)
    key=b"a"*32
    encrypted=gh.encrypt(raw,key)
    assert raw not in encrypted
    assert gh.decrypt(encrypted,key)==raw
    bundle=gh._make_bundle("intersection-github-archive-42340001000-a1",raw)
    assert bundle.temporary is True
    assert bundle.selected_account=="qa-example.bsky.social"
    assert bundle.post_count==1
    account=BundleAccountCloud(bundle)
    items=feed_data(account,bundle.account,0,20)
    assert items["total"]==1
    assert items["posts"][0]["text"]=="Synthetic public account original"
    with pytest.raises(BundleInvalid):
        gh.decrypt(encrypted[:-1]+bytes([encrypted[-1]^1]),key)
    with pytest.raises(BundleInvalid):
        gh.decrypt(encrypted,b"b"*32)


def test_release_rejects_wrong_asset_and_digest(monkeypatch):
    raw=create_synthetic_zip(monkeypatch)
    key=b"z"*32
    payload=gh.encrypt(raw,key)
    digest=hashlib.sha256(payload).hexdigest()
    tag="intersection-github-archive-42340001000-a1"
    release={"tag_name":tag,"draft":False,"prerelease":True,
             "assets":[{"name":"account.enc","id":929209091,"size":len(payload),
             "browser_download_url":"https://github.com/koith/browser-app-lab/releases/download/"+tag+"/account.enc",
             "digest":"sha256:"+digest}]}
    monkeypatch.setattr(gh,"_download",lambda asset:payload)
    bundle=gh.release_bundle(release,key=key)
    assert bundle.object_count>1
    gh._cache.clear()
    release["assets"][0]["browser_download_url"]="https://evil.invalid/account.enc"
    with pytest.raises(BundleInvalid):
        gh.release_bundle(release,key=key)
    release["assets"][0]["browser_download_url"]="https://github.com/koith/browser-app-lab/releases/download/"+tag+"/account.enc"
    monkeypatch.setattr(gh,"_download",lambda asset:payload[:-1]+bytes([payload[-1]^1]))
    gh._cache.clear()
    with pytest.raises(BundleInvalid):
        gh.release_bundle(release,key=key)


def test_run_bundle_does_not_promote_unsupported_workflow_status(monkeypatch):
    monkeypatch.setattr(gh,"releases",lambda max_pages=2:iter(()))
    assert gh.run_bundle(42340001000) is None
    with pytest.raises(ValueError):
        gh.run_bundle(-1)


def test_github_enabled_only_when_explicit(monkeypatch):
    monkeypatch.delenv("DEMAND_ACCOUNT_TEMP_STORAGE",raising=False)
    assert not gh.enabled()
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    assert gh.enabled()


def test_live_viewer_does_not_depend_on_github_rest_api_rate_limit(monkeypatch):
    import io
    from urllib.request import Request
    tag="intersection-github-archive-42340001000-a1"
    atom=('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
          '<entry><link rel="alternate" href="https://github.com/koith/browser-app-lab/'
          'releases/tag/'+tag+'"/></entry></feed>').encode()
    original=create_synthetic_zip(monkeypatch)
    key=b"f"*32
    ciphertext=gh.encrypt(original,key)
    queried=[]
    class Response:
        def __init__(self,data):self.data=data
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self,limit=0):return self.data[:limit] if limit else self.data
    def fake_fetch(request,timeout):
        url=request.full_url
        queried.append(url)
        if url==gh.ATOM:return Response(atom)
        if url=="https://github.com/koith/browser-app-lab/releases/download/"+tag+"/account.enc":
            return Response(ciphertext)
        raise AssertionError("unexpected GitHub REST API request")
    gh._cache.clear()
    gh._feed_cache.update(at=0.0,items=())
    monkeypatch.setattr(gh,"urlopen",fake_fetch)
    found=list(gh.releases())
    assert len(found)==1 and found[0]["_public_atom"] is True
    bundle=gh.release_bundle(found[0],key=key)
    assert bundle.post_count==1
    assert len(queried)==2
    assert all(not u.startswith(gh.API) for u in queried)


def test_tampered_github_release_cdn_cipher_is_rejected(monkeypatch):
    tag="intersection-github-archive-42340001000-a1"
    plain=create_synthetic_zip(monkeypatch)
    cipher=bytearray(gh.encrypt(plain,b"c"*32))
    cipher[-1]^=1
    gh._cache.clear()
    monkeypatch.setattr(gh,"_download_public_tag",lambda _:bytes(cipher))
    with pytest.raises(BundleInvalid):
        gh.release_bundle({"tag_name":tag,"_public_atom":True},key=b"c"*32)
