"""Offline ZIP-staging tests: no network, source account or private TeraBox."""
import json
from pathlib import Path
import zipfile

import pytest
from target_account_bundle import BundleCloud, BundleStore, make_zip, execute_bundle
from test_target_account_archive import BlueAPI, blue_row, cid, DID, PHOTO, VIDEO


@pytest.fixture(autouse=True)
def no_fake_cloud_latency(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-unit-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def test_verified_bundle_contains_profile_original_posts_media_graph_threads(tmp_path):
    p=blue_row("bundle001","Synthetic reviewed public post",
               assets=[("image/jpeg",PHOTO),("video/mp4",VIDEO)])
    api=BlueAPI({None:([p],None)})
    api.blobs={cid(PHOTO):("image/jpeg",PHOTO),cid(VIDEO):("video/mp4",VIDEO)}
    receipts=[]

    def fake_private_remote(package,*,run_id,account_hash):
        assert run_id=="123456789"
        assert account_hash
        with zipfile.ZipFile(package) as archive:
            manifest=json.loads(archive.read("bundle-manifest.json"))
            keys=[item["key"] for item in manifest["objects"]]
            assert any("/posts/" in key and key.endswith("/post.json") for key in keys)
            assert any("metadata/source-records" in key for key in keys)
            assert any("/media/" in key for key in keys)
            assert any("/profile/snapshots/" in key for key in keys)
            assert any("/graph/pages/" in key for key in keys)
            assert any("/threads/" in key for key in keys)
            import hashlib
            for item in manifest["objects"]:
                assert hashlib.sha256(archive.read(item["key"])).hexdigest()==item["sha256"]
            receipts.append(manifest)
        return {"state":"SYNTHETIC_ONLY","bytes":package.stat().st_size}

    result=execute_bundle(selected={"platform":"bluesky",
               "account":"qa-example.bsky.social","max_pages":2},
               api=api,run_id="123456789",cloud_check=False,
               uploader=fake_private_remote)
    assert result["public_posts_in_bundle"]==1
    assert receipts and len(receipts[0]["objects"])>8


def test_buffer_never_overwrites_existing_source_and_bounds_staging():
    store=BundleStore(limit=10)
    assert store.write("metadata/example.json",b"abc") is True
    assert store.write("metadata/example.json",b"abc") is False
    with pytest.raises(RuntimeError,match="collision"):
        store.write("metadata/example.json",b"xyz")
    with pytest.raises(RuntimeError,match="bounded"):
        store.write("metadata/other.json",b"x"*11)
    with pytest.raises(ValueError):
        store.write("../unsafe",b"x")


def test_bundle_snapshot_paths_are_immutable_and_discoverable(tmp_path):
    store=BundleStore()
    cloud=BundleCloud(store,"account-archives/bluesky/abc/")
    cloud.write_immutable("metadata/entries/"+"a"*40+".json",b"test")
    assert cloud.names("metadata/entries")==["a"*40+".json"]
    with pytest.raises(RuntimeError,match="collision"):
        cloud.write_immutable("metadata/entries/"+"a"*40+".json",b"changed")
    out=tmp_path/"test.zip"
    summary=make_zip(store,out,state="RESUME_NEEDED",
                     selected={"platform":"bluesky","account":"example.bsky.social"})
    assert len(summary["objects"])==1
    with zipfile.ZipFile(out) as archive:
        assert archive.read(summary["objects"][0]["key"])==b"test"


def test_authenticated_manual_workflow_account_inputs_queue_verified_zip(monkeypatch):
    monkeypatch.setenv("TARGET_PLATFORM","bluesky")
    monkeypatch.setenv("TARGET_ACCOUNT","qa-example.bsky.social")
    monkeypatch.setenv("TARGET_MAX_PAGES","1")
    post=blue_row("manual001","synthetic manual workflow original")
    api=BlueAPI({None:([post],None)})
    seen=[]
    def simulated_remote(package,*,run_id,account_hash):
        assert run_id=="123456789"
        seen.append(account_hash)
        return {"state":"SYNTHETIC_ONLY","bytes":package.stat().st_size}
    result=execute_bundle(api=api,run_id="123456789",cloud_check=False,
                          uploader=simulated_remote)
    assert result["public_posts_in_bundle"]==1
    assert seen


def test_authenticated_workflow_rejects_unsafe_account_before_upload(monkeypatch):
    monkeypatch.setenv("TARGET_PLATFORM","bluesky")
    monkeypatch.setenv("TARGET_ACCOUNT","javascript:invalid")
    monkeypatch.setenv("TARGET_MAX_PAGES","2")
    with pytest.raises(ValueError):
        execute_bundle(cloud_check=False)
