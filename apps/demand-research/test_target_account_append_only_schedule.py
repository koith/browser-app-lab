"""Synthetic monotonic account refresh: no provider, cloud or real account data."""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from target_account_bundle import (BundleStore,seed_verified_immutable_bundle,
    execute_bundle,execute_registered_schedule,latest_registered_github_bundles)
from test_target_account_archive import BlueAPI,blue_row,DID
from verified_bundle_reader import VerifiedBundle


@pytest.fixture(autouse=True)
def temp_release_lane(monkeypatch):
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def original_bundle(api,run_id="123456789"):
    saved=[]
    def fake_remote(zip_path,*,run_id,account_hash):
        raw=Path(zip_path).read_bytes()
        saved.append((raw,account_hash,run_id))
        return {"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
    result=execute_bundle(selected={"platform":"bluesky",
              "account":"qa-example.bsky.social","max_pages":1},
          api=api,run_id=run_id,cloud_check=False,uploader=fake_remote)
    raw,account_hash,_=saved[0]
    digest=hashlib.sha256(raw).hexdigest()
    name="account-bundle-"+account_hash[:16]+"-"+run_id+"-"+digest[:16]+".zip"
    return VerifiedBundle(name,raw),result


def test_append_only_next_backup_inherits_exact_prior_bytes_and_new_edit(monkeypatch):
    first=blue_row("archivefirst01","Original source is immutable")
    old,stats=original_bundle(BlueAPI({None:([first],None)}))
    assert stats["public_posts_in_bundle"]==1
    old_items=dict(old.items)
    modified=blue_row("archivefirst01","Edited public source retained separately")
    new_post=blue_row("archivenew002","Brand new public source")
    new_api=BlueAPI({None:([new_post,modified],None)})
    saved=[]
    def fake_remote(path,*,run_id,account_hash):
        raw=Path(path).read_bytes()
        saved.append((raw,account_hash,run_id))
        return {"bytes":len(raw)}
    outcome=execute_bundle(selected={"platform":"bluesky",
            "account":"qa-example.bsky.social","max_pages":1},
            api=new_api,run_id="123456790",cloud_check=False,
            uploader=fake_remote,prior_bundle=old)
    assert outcome["prior_objects_preserved"]==len(old_items)
    assert outcome["new_posts"]==1
    assert outcome["new_revisions"]==1
    assert outcome["public_posts_in_bundle"]==2
    newer,hash_part,run=saved[0]
    candidate=VerifiedBundle("account-bundle-"+hash_part[:16]+"-"+
                             run+"-"+hashlib.sha256(newer).hexdigest()[:16]+".zip",
                             newer)
    assert candidate.account==old.account
    for key,bytes_before in old_items.items():
        assert candidate.items[key]==bytes_before
    revisions=[key for key in candidate.items if "/revisions/" in key]
    assert len(revisions)==1
    entry=json.loads(candidate.items[revisions[0]])
    assert entry["text"]=="Edited public source retained separately"
    assert json.loads(next(body for key,body in old_items.items()
            if key.endswith("/post.json")))["text"]=="Original source is immutable"


def test_registered_schedule_rotates_without_treating_tag_as_identity(monkeypatch):
    from types import SimpleNamespace
    import target_account_bundle as b
    from github_temp_bundle import _oidc_key
    monkeypatch.setattr("github_temp_bundle._oidc_key",lambda:b"k"*32)
    bundle,stats=original_bundle(
        BlueAPI({None:([blue_row("savedtest001","One verified public post")],None)}))
    def fake_remote(path,*,run_id,account_hash):
        return {"bytes":Path(path).stat().st_size}
    outcome=execute_registered_schedule(
        api=BlueAPI({None:([blue_row("savedtest001","One verified public post")],None)}),
        run_id="123456791",choose=0,
        fetch_bundles=lambda key:[bundle],uploader=fake_remote)
    assert outcome["prior_objects_preserved"]==len(bundle.items)
    assert outcome["new_posts"]==0
    assert outcome["new_revisions"]==0


def test_seeding_rejects_unverified_or_mixed_account_payloads():
    with pytest.raises(ValueError):
        seed_verified_immutable_bundle(BundleStore(),object())


def test_no_verified_account_schedule_fails_without_initial_review(monkeypatch):
    import target_account_bundle as b
    monkeypatch.setattr("github_temp_bundle._oidc_key",lambda:b"k"*32)
    monkeypatch.setattr(b,"read_bootstrap_request",lambda:None)
    with pytest.raises(RuntimeError,match="no verified registered"):
        execute_registered_schedule(
            fetch_bundles=lambda key:[],choose=0)


def test_bounded_release_scan_accepts_only_verified_bundles(monkeypatch):
    import github_temp_bundle
    bundle,_=original_bundle(BlueAPI({None:([blue_row("registry01","Verified")],None)}))
    monkeypatch.setattr(github_temp_bundle,"releases",lambda max_pages:[
        {"tag_name":"bad-unverified"}, {"tag_name":"good-verified"}])
    def reader(release,key):
        if release["tag_name"]=="bad-unverified":
            raise RuntimeError("tampered AES")
        assert key==b"k"*32
        return bundle
    monkeypatch.setattr(github_temp_bundle,"release_bundle",reader)
    found=latest_registered_github_bundles(b"k"*32)
    assert len(found)==1 and found[0].account==bundle.account
