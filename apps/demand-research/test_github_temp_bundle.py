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
    monkeypatch.setattr(gh,"tagged_bundle",lambda tag,missing_ok=False:None)
    assert gh.run_bundle(42340001000) is None
    with pytest.raises(ValueError):
        gh.run_bundle(-1)


def test_github_enabled_only_when_explicit(monkeypatch):
    monkeypatch.delenv("DEMAND_ACCOUNT_TEMP_STORAGE",raising=False)
    assert not gh.enabled()
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    assert gh.enabled()


def test_atom_feed_finds_temporary_release_without_github_rest_api(monkeypatch):
    tag="intersection-github-archive-42340001000-a1"
    xml=('<?xml version="1.0" encoding="utf-8"?>'
         '<feed xmlns="http://www.w3.org/2005/Atom">'
         '<entry><title>temporary backup</title><link rel="alternate" '
         'href="https://github.com/koith/browser-app-lab/releases/tag/'+tag+'"/></entry>'
         '<entry><link href="https://github.com/untrusted/other/releases/tag/'+tag+'"/></entry>'
         '</feed>').encode()
    class FakeResponse:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,cap):
            assert cap<=1_000_001
            return xml
    monkeypatch.setattr(gh,"urlopen",lambda *args,**kwargs:FakeResponse())
    assert list(gh.atom_tags())==[tag]


def test_github_direct_tag_reader_authenticates_remote_without_rest_api(monkeypatch):
    raw=create_synthetic_zip(monkeypatch)
    key=b"s"*32
    encrypted=gh.encrypt(raw,key)
    monkeypatch.setattr(gh,"gateway_key",lambda:key)
    monkeypatch.setattr(gh,"_download_tag",lambda tag,missing_ok=False:encrypted)
    monkeypatch.setattr(gh,"_json",lambda *args,**kw:
                        (_ for _ in ()).throw(AssertionError("REST API must not be queried")))
    gh._cache.clear()
    bundle=gh.run_bundle(42340001000,account="qa-example.bsky.social")
    assert bundle is not None
    assert bundle.post_count==1
    assert bundle.temporary is True
    monkeypatch.setattr(gh,"atom_tags",lambda:iter(["intersection-github-archive-42340001000-a1"]))
    assert [b.account for b in gh.latest_bundles()]==[bundle.account]
    gh._cache.clear()
    monkeypatch.setattr(gh,"_download_tag",lambda tag,missing_ok=False:
                        encrypted[:-1]+bytes([encrypted[-1]^1]))
    with pytest.raises(BundleInvalid):
        gh.run_bundle(42340001000)


def test_unrelated_atom_tag_never_enters_selected_account_list(monkeypatch):
    xml=(b'<feed xmlns="http://www.w3.org/2005/Atom">'
         b'<entry><link rel="alternate" href="https://evil.example/release"/></entry>'
         b'</feed>')
    class FakeResponse:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,cap):return xml
    monkeypatch.setattr(gh,"urlopen",lambda *args,**kwargs:FakeResponse())
    assert list(gh.atom_tags())==[]


def test_new_release_waits_for_public_cdn_without_fake_success(monkeypatch):
    from urllib.error import HTTPError
    tag="intersection-github-archive-42360905305-a1"
    payload=b"ciphertext-test-only-"*16
    release={"tag_name":tag,"draft":False,"prerelease":True,
             "assets":[{"name":"account.enc","id":123456,
                        "size":len(payload),
                        "browser_download_url":
                          "https://github.com/koith/browser-app-lab/releases/download/"
                          +tag+"/account.enc",
                        "digest":"sha256:"+hashlib.sha256(payload).hexdigest()}]}
    monkeypatch.setattr(gh,"_json",lambda url,token:release)
    invoked=[]
    def delayed_public_readback(_asset):
        invoked.append(1)
        if len(invoked)<3:
            raise HTTPError("https://github.com/",404,"publishing",{},None)
        return payload
    monkeypatch.setattr(gh,"_download",delayed_public_readback)
    monkeypatch.setattr(gh.time,"sleep",lambda _:None)
    assert gh.readback_uploaded_release(tag,"nonprivate-fixture-token",attempts=3)==payload
    assert len(invoked)==3


def test_release_readback_rejects_403_or_wrong_asset_without_retry(monkeypatch):
    from urllib.error import HTTPError
    tag="intersection-github-archive-42360905305-a1"
    monkeypatch.setattr(gh,"_json",lambda url,token:{
        "tag_name":tag,"draft":False,"prerelease":True,
        "assets":[{"name":"account.enc","id":123456,"size":90,
                   "browser_download_url":
                       "https://github.com/koith/browser-app-lab/releases/download/"
                       +tag+"/account.enc"}]})
    calls=[]
    def denied(_asset):
        calls.append(1)
        raise HTTPError("https://github.com/",403,"forbidden",{},None)
    monkeypatch.setattr(gh,"_download",denied)
    monkeypatch.setattr(gh.time,"sleep",lambda _:pytest.fail("403 must not retry"))
    with pytest.raises(RuntimeError,match="readback denied"):
        gh.readback_uploaded_release(tag,"nonprivate-fixture-token")
    assert len(calls)==1
    monkeypatch.setattr(gh,"_json",lambda url,token:{
        "tag_name":tag,"draft":False,"prerelease":True,
        "assets":[{"name":"account.enc","id":123456,"size":90,
                   "browser_download_url":"https://evil.invalid/asset.enc"}]})
    with pytest.raises(BundleInvalid):
        gh.readback_uploaded_release(tag,"nonprivate-fixture-token")
    assert len(calls)==1


def test_multiple_signed_history_zips_stay_cached_without_repeat_download(
        monkeypatch):
    """An account's six incremental ZIPs cannot evict one another every tab."""
    raw=create_synthetic_zip(monkeypatch)
    secret=b"q"*32
    ciphertext=gh.encrypt(raw,secret)
    monkeypatch.setattr(gh,"gateway_key",lambda:secret)
    reads=[]
    def download(tag,missing_ok=False):
        reads.append(tag)
        return ciphertext
    monkeypatch.setattr(gh,"_download_tag",download)
    gh._cache.clear()
    tags=["intersection-github-archive-42340001000-a"+str(i)
          for i in range(1,7)]
    try:
        for tag in tags:
            assert gh.tagged_bundle(tag).post_count==1
        assert len(reads)==6
        for tag in reversed(tags):
            assert gh.tagged_bundle(tag).post_count==1
        assert len(reads)==6,"six SHA-authenticated ancestors must be cached"
        assert len(gh._cache)==6
        assert sum(gh._bundle_bytes(v[1]) for v in gh._cache.values())<=(
            gh.MAX_VERIFIED_CACHE_BYTES)
    finally:
        gh._cache.clear()


def test_verified_zip_lru_enforces_strict_memory_budget(monkeypatch):
    """No later ZIP can grow the free Render process cache without bound."""
    raw=create_synthetic_zip(monkeypatch)
    secret=b"q"*32
    ciphertext=gh.encrypt(raw,secret)
    monkeypatch.setattr(gh,"gateway_key",lambda:secret)
    seen=[]
    monkeypatch.setattr(gh,"_download_tag",
        lambda tag,missing_ok=False:seen.append(tag) or ciphertext)
    gh._cache.clear()
    monkeypatch.setattr(gh,"MAX_VERIFIED_CACHE_BYTES",len(raw)*2+8)
    tags=["intersection-github-archive-42340001100-a"+str(i)
          for i in range(1,4)]
    try:
        for tag in tags:gh.tagged_bundle(tag)
        assert len(gh._cache)==2
        assert sum(gh._bundle_bytes(v[1]) for v in gh._cache.values())<=(
            gh.MAX_VERIFIED_CACHE_BYTES)
        gh.tagged_bundle(tags[0])
        assert len(seen)==4,"evicted older source must reauthenticate"
    finally:
        gh._cache.clear()


def test_invalid_zip_must_never_enter_verified_lru(monkeypatch):
    raw=create_synthetic_zip(monkeypatch)
    encrypted=gh.encrypt(raw,b"q"*32)
    tag="intersection-github-archive-42340001200-a1"
    gh._cache.clear()
    monkeypatch.setattr(gh,"gateway_key",lambda:b"q"*32)
    monkeypatch.setattr(gh,"_download_tag",lambda tag,missing_ok=False:
                        encrypted[:-1]+bytes([encrypted[-1]^1]))
    with pytest.raises(BundleInvalid):
        gh.tagged_bundle(tag)
    assert gh._cache=={}
