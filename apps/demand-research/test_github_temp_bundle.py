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
