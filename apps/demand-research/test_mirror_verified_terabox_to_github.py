"""Credential-free regression tests of immutable TeraBox -> encrypted GH mirror."""
from pathlib import Path
import hashlib

import pytest

import github_temp_bundle as gh
import mirror_verified_terabox_to_github as mirror
from demand_archive import sha256
from target_account_archive import archive_key, run_one
from target_account_bundle import BundleStore, BundleCloud, bundle_factory, make_zip
from test_target_account_archive import BlueAPI, blue_row, cid, DID, PHOTO
from test_demand_archive import FakeCloud


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    store=BundleStore()
    api=BlueAPI({None:([blue_row("mirror001","test synthetic public post",
                  assets=[("image/jpeg",PHOTO)])],None)})
    api.blobs={cid(PHOTO):("image/jpeg",PHOTO)}
    result=run_one("bluesky","synthetic-mirror.bsky.social",root=BundleCloud(store),
                   api=api,max_pages=2,clock=lambda:0,
                   archive_factory=bundle_factory)
    assert result["posts_verified"]==1
    file=tmp_path/"source.zip"
    make_zip(store,file,state=result["status"],
             selected={"platform":"bluesky","account":"synthetic-mirror.bsky.social"})
    raw=file.read_bytes()
    account_hash=archive_key({"platform":"bluesky","identity":DID})
    name="account-bundle-"+account_hash[:16]+"-123456789-"+sha256(raw)[:16]+".zip"
    root=FakeCloud()
    root.objects[name]=raw
    return root,name,raw,account_hash


def test_source_requires_exact_run_and_all_originals_have_valid_sha(prepared):
    root,name,raw,_=prepared
    found=mirror.load_source(root,"123456789")
    assert found.name==name and found.contents==raw
    assert found.bundle.post_count==1 and found.bundle.object_count>1
    with pytest.raises(RuntimeError):
        mirror.load_source(root,"123456788")
    with pytest.raises(RuntimeError):
        mirror.load_source(root,"123456789",minimum_posts=2)
    with pytest.raises(ValueError):
        mirror.load_source(root,"../123456789")
    root.objects[name]=raw[:-12]+b"tampered-byte"
    with pytest.raises((RuntimeError,mirror.BundleInvalid)):
        mirror.load_source(root,"123456789")


def test_mirror_existing_source_shares_no_plaintext_and_sha_verifies(prepared,monkeypatch):
    root,name,raw,account_hash=prepared
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT","2")
    monkeypatch.setattr(gh,"_oidc_key",lambda:b"t"*32)
    monkeypatch.setattr(gh,"_download_tag",lambda *_,**__:None)
    monkeypatch.setattr(gh,"atom_tags",lambda:iter(()))
    called=[]
    def fake_upload(path,*,run_id,account_hash):
        assert Path(path).read_bytes()==raw
        assert run_id=="123456789"
        called.append(account_hash)
        assert len(account_hash)==40
        return {"state":"GITHUB_TEMP_SHA_VERIFIED","bytes":len(raw)+34,
                "sha256":sha256(raw),"key":"intersection-github-archive-123456789-a1"}
    monkeypatch.setattr(gh,"upload_release",fake_upload)
    result=mirror.mirror(source_run="123456789",root=root)
    assert result["state"]=="GITHUB_TEMP_SHA_VERIFIED"
    assert len(called)==1


def test_exact_existing_mirror_is_sha_checked_and_idempotent(prepared,monkeypatch):
    root,name,raw,_=prepared
    key=b"t"*32
    monkeypatch.setattr(gh,"_oidc_key",lambda:key)
    monkeypatch.setattr(gh,"_download_tag",lambda tag,missing_ok=False:b"encrypted")
    monkeypatch.setattr(gh,"decrypt",lambda raw_cipher,private_key:raw)
    def no_upload(*_,**__):
        raise AssertionError("same archive must not be uploaded twice")
    monkeypatch.setattr(gh,"upload_release",no_upload)
    result=mirror.mirror(source_run="123456789",root=root)
    assert result["state"]=="ALREADY_SHA_VERIFIED"


def test_skip_weaker_snapshot_when_stronger_github_archive_exists(prepared,monkeypatch):
    root,name,raw,_=prepared
    account=mirror.load_source(root,"123456789").bundle.account
    monkeypatch.setattr(gh,"_oidc_key",lambda:b"t"*32)
    tag="intersection-github-archive-987654321-a1"
    monkeypatch.setattr(gh,"_download_tag",lambda value,missing_ok=False:
                        None if value.endswith("123456789-a1") else b"existing")
    monkeypatch.setattr(gh,"atom_tags",lambda:iter([tag]))
    monkeypatch.setattr(gh,"decrypt",lambda *_:raw)
    def no_upload(*_,**__):
        raise AssertionError("no downgrade permitted")
    monkeypatch.setattr(gh,"upload_release",no_upload)
    result=mirror.mirror(source_run="123456789",root=root)
    assert result["state"]=="ALREADY_MORE_COMPLETE"


def test_published_but_cdn_delayed_existing_mirror_is_not_uploaded_twice(
        prepared,monkeypatch):
    root,_name,raw,_hash=prepared
    key=b"t"*32
    source=mirror.load_source(root,"123456789").bundle
    wrapped=gh.encrypt(raw,key)
    monkeypatch.setenv("GITHUB_TOKEN","test-job-token-never-networked")
    monkeypatch.setattr(gh,"_oidc_key",lambda:key)
    monkeypatch.setattr(gh,"_download_tag",lambda tag,missing_ok=False:None)
    visited=[]
    monkeypatch.setattr(gh,"_json",lambda url,token:
                        (visited.append((url,token)) or {"tag_name":
                         "intersection-github-archive-123456789-a1"}))
    monkeypatch.setattr(gh,"readback_uploaded_release",
                        lambda tag,token:wrapped)
    monkeypatch.setattr(gh,"upload_release",
                        lambda *args,**kwargs:pytest.fail(
                            "never recreate an existing immutable release"))
    result=mirror.mirror(source_run="123456789",root=root)
    assert result["state"]=="ALREADY_SHA_VERIFIED"
    assert result["posts"]==source.post_count
    assert len(visited)==1
