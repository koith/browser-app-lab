"""Credential-free safety, authenticity and restoration tests for AES-GCM spool."""
import hashlib
import os

import pytest

from demand_archive import canonical_json, post_key, sha256
from recovery_spool import RecoverySpool, recover_directory
from test_demand_archive import FakeCloud, post as synthetic_post
import demand_capture_job as job


@pytest.fixture(autouse=True)
def synthetic_configuration(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_RECOVERY_KEY","synthetic-random-test-password-long-enough-256")
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-tb-cookie-with-sufficient-entropy")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def first(pid):
    return {"id":pid,"platform":"bluesky","text":"PRIVATE TEST BODY sentinel-327849",
            "posted_at":"2026-11-03T00:00:00Z",
            "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/synthetic",
            "observed_at":1793667600,"media_links":[],
            "profile_url":"https://bsky.app/profile/did:plc:abcdefghijk"}


def test_ciphertext_artifact_never_contains_original_text_or_source_url(tmp_path):
    p=synthetic_post()
    pid=p["id"]
    spool=RecoverySpool(tmp_path)
    file=spool.save(pid,first(pid))
    raw=file.read_bytes()
    assert raw.startswith(b"INTSP1")
    assert b"PRIVATE TEST BODY" not in raw
    assert b"bsky.app" not in raw
    assert pid.encode() not in raw
    assert file.stat().st_mode & 0o777 == 0o600
    assert spool.read(file)["first"]==first(pid)


def test_tampering_and_wrong_secret_are_detected_before_remote_writes(tmp_path):
    p=synthetic_post()
    pid=p["id"]
    spool=RecoverySpool(tmp_path)
    file=spool.save(pid,first(pid))
    raw=file.read_bytes()
    file.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
    cloud=FakeCloud()
    counts=recover_directory(tmp_path,cloud)
    assert counts["buffer_files"]==1
    assert counts["failures"]==1
    assert cloud.objects=={}
    file.write_bytes(raw)
    with pytest.raises(Exception):
        RecoverySpool(tmp_path,secret=b"another-unrelated-private-secret-value").read(file)


def test_restore_exact_original_media_after_temporary_terabox_unavailability(tmp_path):
    p=synthetic_post()
    pid=p["id"]
    source=first(pid)
    blob=b"\\x89PNG\\r\\n\\x1a\\n synthetic original capture 1"
    # A JPEG MIME is used only as synthetic metadata, not as a visible image.
    p["media"]=[{"key":"posts/"+pid+"/media/0001.jpg","mime":"image/jpeg",
                 "bytes":len(blob),"sha256":sha256(blob),"remote_verified":True}]
    spool=RecoverySpool(tmp_path)
    spool.save(pid,source,p,[blob])
    cloud=FakeCloud()
    counts=recover_directory(tmp_path,cloud)
    assert counts["post_and_media_verified"]==1
    assert counts["failures"]==0
    assert cloud.objects["posts/"+pid+"/media/0001.jpg"]==blob
    assert cloud.load_catalog()[0]["id"]==pid
    assert cloud.read_first_observation(pid)==canonical_json(source)
    # Idempotent replay must not duplicate or replace immutable originals.
    again=recover_directory(tmp_path,cloud)
    assert again["post_and_media_verified"]==1
    assert cloud.objects["posts/"+pid+"/media/0001.jpg"]==blob


def test_fast_capture_spools_failed_cloud_observation_and_can_replay(tmp_path,monkeypatch):
    class FirstWriteUnavailable(FakeCloud):
        def save_first_observation(self,*args,**kwargs):
            raise RuntimeError("test-only private backend missing")
    cloud=FirstWriteUnavailable()
    monkeypatch.setenv("DEMAND_RECOVERY_SPOOL_DIR",str(tmp_path))
    original_id="at://did:plc:abcdefghijk/app.bsky.feed.post/synthetic"
    row={"platform":"bluesky","original_id":original_id,
         "text":"PRIVATE TEST BODY sentinel-327849",
         "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/synthetic",
         "posted_at":"2026-11-03T00:00:00Z","media_urls":[],"media_expected":0}
    res=job.run(fetchers=[
        lambda term,start,end:[row] if term==job.TERMS[0] else []],
        cloud=cloud,clock=lambda:1793667900,run_id="123456832",fast_mode=True)
    assert res["storage_failures"]==1
    assert res["encrypted_recovery_files"]==1
    assert cloud.objects=={}
    names=list(tmp_path.glob("*.enc"))
    assert len(names)==1
    assert b"PRIVATE TEST BODY" not in names[0].read_bytes()
    repaired=FakeCloud()
    stats=recover_directory(tmp_path,repaired)
    assert stats["first_observation_verified"]==1
    pid=post_key("bluesky",original_id)
    assert repaired.read_first_observation(pid) is not None
    assert repaired.load_catalog()==[]


def test_verified_capture_drops_encrypted_transient_buffer(tmp_path,monkeypatch):
    cloud=FakeCloud()
    monkeypatch.setenv("DEMAND_RECOVERY_SPOOL_DIR",str(tmp_path))
    original_id="at://did:plc:abcdefghijk/app.bsky.feed.post/synthetic"
    row={"platform":"bluesky","original_id":original_id,
         "text":"synthetic "+job.TERMS[0],
         "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/synthetic",
         "posted_at":"2026-11-03T00:00:00Z","media_urls":[],"media_expected":0}
    outcome=job.run(fetchers=[
        lambda term,start,end:[row] if term==job.TERMS[0] else []],
        cloud=cloud,clock=lambda:1793667900,run_id="123456833",fast_mode=True)
    assert outcome["storage_failures"]==0
    assert outcome["saved_verified"]==1
    assert not list(tmp_path.glob("*.enc"))
