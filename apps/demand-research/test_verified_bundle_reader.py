"""Private gateway integration tests using a remote-shaped synthetic ZIP only."""
from __future__ import annotations
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient

import gateway
import target_account_viewer as viewer
import verified_bundle_reader as bundles
from target_account_archive import run_one, archive_key, post_key
from target_account_bundle import BundleStore, BundleCloud, bundle_factory, make_zip
from test_target_account_archive import BlueAPI, blue_row, cid, DID, PHOTO
from test_demand_archive import FakeCloud
from demand_archive import sha256


@pytest.fixture
def private_zip_client(monkeypatch,tmp_path):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-not-a-real-cookie")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    store=BundleStore()
    jobroot=BundleCloud(store)
    p=blue_row("zipreader1","A synthetic archived public source post",
               assets=[("image/jpeg",PHOTO)])
    api=BlueAPI({None:([p],None)})
    api.blobs={cid(PHOTO):("image/jpeg",PHOTO)}
    result=run_one("bluesky","qa-example.bsky.social",root=jobroot,api=api,
                   max_pages=2,clock=lambda:0,archive_factory=bundle_factory)
    assert result["posts_verified"]==1
    package=tmp_path/"bundle.zip"
    make_zip(store,package,state=result["status"],
             selected={"platform":"bluesky","account":"qa-example.bsky.social"})
    raw=package.read_bytes()
    meta={"platform":"bluesky","identity":DID}
    hash40=archive_key(meta)
    remote_name="account-bundle-"+hash40[:16]+"-123456789-"+sha256(raw)[:16]+".zip"
    root=FakeCloud()
    root.objects[remote_name]=raw
    monkeypatch.setattr(viewer,"open_root",lambda:root)
    monkeypatch.setattr(bundles,"_cache",{})
    monkeypatch.setattr(gateway,"TOKEN","synthetic-viewer-private-link-token-0123456789")
    monkeypatch.setattr(gateway,"COOKIE","synthetic-not-a-real-cookie")
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.post("/api/activate",json={
        "token":"synthetic-viewer-private-link-token-0123456789"}).status_code==200
    return client,root,remote_name,p,meta


def test_verified_zip_is_listed_and_readable_with_original_media(private_zip_client):
    client,root,name,post,meta=private_zip_client
    account="bluesky-"+archive_key(meta)
    listing=client.get("/api/account-archives")
    assert listing.status_code==200,listing.text
    entries=listing.json()["accounts"]
    assert len(entries)==1 and entries[0]["key"]==account
    assert entries[0]["backup_kind"]=="terabox_zip_sha_verified"
    receipt=client.get("/api/account-archives/"+account+"/backup-status")
    assert receipt.status_code==200
    assert receipt.json()["state"]=="REMOTE_ZIP_SHA_VERIFIED"
    assert receipt.json()["public_posts"]==1
    prof=client.get("/api/account-archives/"+account+"/profile")
    assert prof.status_code==200 and prof.json()["available"]
    assert client.get(prof.json()["assets"]["avatar"]).status_code==200
    feed=client.get("/api/account-archives/"+account+"/feed")
    assert feed.status_code==200,feed.text
    rows=feed.json()["posts"]
    assert len(rows)==1 and rows[0]["text"]=="A synthetic archived public source post"
    photo=client.get(rows[0]["media"][0]["url"])
    assert photo.status_code==200 and photo.content==PHOTO
    partial=client.get(rows[0]["media"][0]["url"],headers={"Range":"bytes=0-5"})
    assert partial.status_code==206 and partial.content==PHOTO[:6]
    for kind in ("followers","following"):
        graph=client.get("/api/account-archives/"+account+"/graph/"+kind)
        assert graph.status_code==200 and graph.json()["captured_unique"]==1
    replies=client.get("/api/account-archives/"+account+"/threads/"+rows[0]["id"])
    assert replies.status_code==200 and replies.json()["captured"] is True
    # No private data appears on the unauthenticated public route.
    not_logged=TestClient(gateway.app,base_url="https://testserver")
    assert not_logged.get("/api/account-archives").status_code==401


def test_mutated_bundle_bytes_do_not_create_false_verified_account(private_zip_client):
    client,root,name,post,meta=private_zip_client
    bytes_=bytearray(root.objects[name])
    bytes_[-9]^=1
    root.objects[name]=bytes(bytes_)
    bundles._cache.clear()
    result=client.get("/api/account-archives")
    assert result.status_code==200
    assert result.json()["accounts"]==[]


def test_manifest_claims_only_one_isolated_account(private_zip_client):
    client,root,name,post,meta=private_zip_client
    bundle=bundles.load_verified_bundle(root,name)
    assert bundle.account=="bluesky-"+archive_key(meta)
    assert bundle.post_count==1 and bundle.object_count>=8
    assert bundle.source_state=="COMPLETE_CURRENT_PUBLIC_CURSOR"


def test_live_job_status_reads_exact_remote_run_zip_not_just_green_actions(
        private_zip_client,monkeypatch):
    import target_archive_api as archive_api
    client,root,filename,post,profile=private_zip_client
    run_id=123456789
    monkeypatch.setattr(archive_api,"CloudArchive",lambda remote:root)
    bundles._cache.clear()
    verified=archive_api.read_exact_verified_archive(
        run_id,"bluesky","qa-example.bsky.social")
    assert verified["state"]=="REMOTE_VERIFIED"
    assert verified["remote_verified"] is True
    assert verified["posts"]==1
    assert verified["objects"]>=8
    assert verified["account_key"]=="bluesky-"+archive_key(profile)
    assert archive_api.read_exact_verified_archive(
        run_id,"bluesky","wrong-public.bsky.social") is None
    assert archive_api.read_exact_verified_archive(
        run_id+1,"bluesky","qa-example.bsky.social") is None
    root.objects[filename]=root.objects[filename][:-13]+b"altered original"
    bundles._cache.clear()
    with pytest.raises(bundles.BundleInvalid):
        archive_api.read_exact_verified_archive(
            run_id,"bluesky","qa-example.bsky.social")


def test_many_snapshots_selects_latest_verified_one_per_account(
        private_zip_client):
    client,root,filename,post,profile=private_zip_client
    old=filename.replace("-123456789-","-123456788-")
    root.objects[old]=root.objects[filename]
    bundles._cache.clear()
    current=list(bundles.available_bundles(root))
    assert len(current)==1
    assert current[0].name==filename


def test_verified_zip_library_survives_broken_nested_legacy_registry(private_zip_client):
    client,root,filename,post,profile=private_zip_client
    runner=root.runner
    def unavailable_old_registry(args,data=None,timeout=150,allow_missing=False):
        if args[0]=="lsf" and "/metadata/target-accounts" in args[1]:
            raise RuntimeError("old nested registry unavailable")
        return runner(args,data=data,timeout=timeout,allow_missing=allow_missing)
    root.runner=unavailable_old_registry
    bundles._cache.clear()
    response=client.get("/api/account-archives")
    assert response.status_code==200,response.text
    assert len(response.json()["accounts"])==1
    assert response.json()["accounts"][0]["backup_kind"]=="terabox_zip_sha_verified"


def test_live_storage_mix_prefers_more_complete_sha_verified_terabox(
        private_zip_client,monkeypatch):
    """The real ZIP must be visible even with GitHub temporary mode enabled."""
    client,root,name,post,meta=private_zip_client
    account="bluesky-"+archive_key(meta)
    complete=bundles.load_verified_bundle(root,name)
    # This is a previously verified but less complete temporary snapshot.
    # Actual account ZIP bytes and media still come from fixture's TeraBox root.
    from types import SimpleNamespace
    older=SimpleNamespace(account=account,selected_platform="bluesky",
          accounts={account:complete.accounts[account]},post_count=0,
          object_count=0,source_state="SOURCE_PARTIAL")
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    monkeypatch.setattr(viewer.github_temp_bundle,"latest_bundles",lambda:[older])
    monkeypatch.setattr(viewer.github_temp_bundle,"account_bundle",
                        lambda key:older if key==account else None)
    response=client.get("/api/account-archives")
    assert response.status_code==200,response.text
    rows=response.json()["accounts"]
    assert len(rows)==1
    assert rows[0]["backup_kind"]=="terabox_zip_sha_verified"
    assert rows[0]["posts_verified_in_bundle"]==1
    assert rows[0]["temporary"] is False
    receipt=client.get("/api/account-archives/"+account+"/backup-status")
    assert receipt.status_code==200 and receipt.json()["storage"]=="private_terabox"
    feed=client.get("/api/account-archives/"+account+"/feed")
    assert feed.status_code==200 and feed.json()["total"]==1
    media=feed.json()["posts"][0]["media"][0]["url"]
    assert client.get(media).content==PHOTO


def test_live_storage_mix_keeps_github_usable_when_terabox_fails(
        private_zip_client,monkeypatch):
    """A provider 403 or slow read cannot erase an independently verified backup."""
    client,root,name,post,meta=private_zip_client
    account="bluesky-"+archive_key(meta)
    temporary=bundles.load_verified_bundle(root,name)
    temporary.temporary=True
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    monkeypatch.setattr(viewer.github_temp_bundle,"latest_bundles",lambda:[temporary])
    monkeypatch.setattr(viewer.github_temp_bundle,"account_bundle",
                        lambda key:temporary if key==account else None)
    def failed_source(_root):
        raise RuntimeError("synthetic unavailable provider; never log remote")
        yield
    monkeypatch.setattr(viewer,"_verified_account_bundles",failed_source)
    rows=client.get("/api/account-archives")
    assert rows.status_code==200 and len(rows.json()["accounts"])==1
    assert rows.json()["accounts"][0]["backup_kind"]=="github_temp_sha_verified"
    feed=client.get("/api/account-archives/"+account+"/feed")
    assert feed.status_code==200 and feed.json()["total"]==1
    assert client.get(feed.json()["posts"][0]["media"][0]["url"]).content==PHOTO


def test_live_storage_mix_keeps_terabox_when_github_index_fails(
        private_zip_client,monkeypatch):
    client,root,name,post,meta=private_zip_client
    account="bluesky-"+archive_key(meta)
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    def failed_github():
        raise RuntimeError("synthetic unavailable GitHub API")
    monkeypatch.setattr(viewer.github_temp_bundle,"latest_bundles",failed_github)
    monkeypatch.setattr(viewer.github_temp_bundle,"account_bundle",
                        lambda _key:None)
    listing=client.get("/api/account-archives")
    assert listing.status_code==200
    assert listing.json()["accounts"][0]["backup_kind"]=="terabox_zip_sha_verified"
    assert client.get("/api/account-archives/"+account+"/feed").json()["total"]==1


def test_bounded_zip_source_preserves_verified_bytes_and_caps_read_time(capsys):
    class SyntheticRoot:
        remote="archive:DemandResearch"
        def __init__(self):
            self.calls=[]
        def command(self,args,*,data=None,timeout=150,allow_missing=False):
            self.calls.append((args[0],timeout))
            return b"synthetic private ZIP bytes"
    source=SyntheticRoot()
    wrapper=viewer._BoundedZipRoot(source)
    assert wrapper.command(["lsf","SECRET-REMOTE-PATH"],timeout=90)
    assert wrapper.command(["cat","SECRET-REMOTE-PATH"],timeout=180)
    assert source.calls==[("lsf",30),("cat",55)]
    output=capsys.readouterr().out
    assert "INTERSECTION_ZIP_SOURCE_READ" in output
    assert "operation=lsf outcome=ok" in output
    assert "operation=cat outcome=ok" in output
    assert "SECRET-REMOTE-PATH" not in output


def test_bounded_zip_source_auth_denial_is_redacted_and_not_verified(capsys):
    class Denied:
        remote="archive:DemandResearch"
        def command(self,args,*,data=None,timeout=150,allow_missing=False):
            raise RuntimeError("private cloud cat failed (authorization) - SECRET")
    with pytest.raises(RuntimeError,match="authorization"):
        viewer._BoundedZipRoot(Denied()).command(
            ["cat","SECRET-REMOTE-PATH"],timeout=180)
    output=capsys.readouterr().out
    assert "operation=cat outcome=authorization" in output
    assert "SECRET" not in output
