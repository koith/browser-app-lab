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
    source["media_links"]=["https://cdn.bsky.app/img/original-test-only.jpg"]
    p.update({"text":source["text"],"source_url":source["source_url"],
              "posted_at":source["posted_at"],"media_expected":1,
              "media_saved":1,"archive_complete":True})
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
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[
            lambda term,start,end:[row] if term==job.TERMS[0] else []],
            cloud=cloud,clock=lambda:1793667900,run_id="123456832",fast_mode=True)
    assert cloud.objects=={}
    names=list(tmp_path.glob("*.enc"))
    assert len(names)==1
    assert b"PRIVATE TEST BODY" not in names[0].read_bytes()
    repaired=FakeCloud()
    stats=recover_directory(tmp_path,repaired)
    assert stats["post_and_media_verified"]==1
    pid=post_key("bluesky",original_id)
    assert repaired.read_first_observation(pid) is not None
    assert repaired.load_catalog()[0]["id"]==pid


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


def test_repair_entrypoint_replays_encrypted_local_staging_without_source_access(tmp_path):
    from recover_spool_artifacts import replay
    pid=synthetic_post()["id"]
    RecoverySpool(tmp_path).save(pid,first(pid))
    cloud=FakeCloud()
    report=replay(cloud=cloud,local_directory=tmp_path)
    assert report["first_observation_verified"]==1
    assert report["encrypted_buffers"]==1
    assert report["buffer_failures"]==0
    assert cloud.read_first_observation(pid)==canonical_json(first(pid))


def test_artifact_discovery_rejects_unrelated_or_inconsistent_run_names(monkeypatch):
    import json
    import recover_spool_artifacts as mod
    monkeypatch.setenv("GITHUB_REPOSITORY","koith/browser-app-lab")
    seen=[]
    def fake_gh(args,*,max_bytes=2_000_000):
        seen.append(args)
        assert "name=intersection-private-recovery" in args[-1]
        payload={"artifacts":[
           {"name":"unrelated-album","size_in_bytes":1024,"expired":False,
            "workflow_run":{"id":12345601},"created_at":"2026-11-03T10:00:00Z"},
           {"name":"intersection-private-recovery","size_in_bytes":512,"expired":False,
            "workflow_run":{"id":12345602,"repository_id":1284121913,
                            "head_repository_id":1284121913,"head_branch":"main"},
            "created_at":"2026-11-03T10:02:00Z"},
           {"name":"intersection-private-recovery","size_in_bytes":200_000_001,"expired":False,
            "workflow_run":{"id":12345603},"created_at":"2026-11-03T10:03:00Z"},
           {"name":"intersection-private-recovery","size_in_bytes":128,"expired":True,
            "workflow_run":{"id":12345604},"created_at":"2026-11-03T10:04:00Z"}]}
        return json.dumps(payload).encode("utf-8")
    monkeypatch.setattr(mod,"_gh",fake_gh)
    candidates=mod.list_candidates()
    assert len(candidates)==1
    assert candidates[0][1]==12345602
    assert candidates[0][2]=="intersection-private-recovery"
    assert len(seen)==1


def test_mismatched_post_identity_never_restores_unrelated_attachment(tmp_path):
    p=synthetic_post()
    pid=p["id"]
    source=first(pid)
    p["media_expected"]=0
    p["media_saved"]=0
    RecoverySpool(tmp_path).save(pid,source,p,[])
    cloud=FakeCloud()
    result=recover_directory(tmp_path,cloud)
    assert result["failures"]==1
    assert cloud.objects=={}


def test_first_cloud_write_failure_still_captures_exact_media_before_origin_disappears(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    class PrivateCloudUnavailable(FakeCloud):
        def save_first_observation(self,*args,**kwargs):
            raise RuntimeError("synthetic private cloud upload failed")
    bad=PrivateCloudUnavailable()
    monkeypatch.setenv("DEMAND_RECOVERY_SPOOL_DIR",str(tmp_path))
    oid="at://did:plc:abcdefghijk/app.bsky.feed.post/volatile-original"
    pid=post_key("bluesky",oid)
    raw=b"PUBLIC-ORIGINAL-JPEG-BYTES-TEST-42"
    row={"platform":"bluesky","original_id":oid,
         "text":"synthetic verified "+job.TERMS[0],
         "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/volatile-original",
         "posted_at":"2026-11-03T00:00:00Z",
         "media_urls":["https://cdn.bsky.app/img/volatile-original.jpg"],
         "profile_url":"https://bsky.app/profile/did:plc:abcdefghijk",
         "media_expected":1}
    def source_media(current,now,get_media=None,pid_override=None,cloud=None):
        p={"id":pid,"platform":current["platform"],
           "text":current["text"],"source_url":current["source_url"],
           "posted_at":current["posted_at"],
           "captured_at":datetime.fromtimestamp(now,timezone.utc).isoformat(),
           "media_expected":1,"media_saved":1,"archive_complete":True,
           "media":[{"key":"posts/"+pid+"/media/0001.jpg",
                     "mime":"image/jpeg","bytes":len(raw),
                     "sha256":sha256(raw),"remote_verified":True}]}
        return p,[raw]
    monkeypatch.setattr(job,"make_post",source_media)
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end: [row] if term==job.TERMS[0] else []],
                cloud=bad,clock=lambda:1793667900,run_id="123456834",fast_mode=True)
    assert bad.objects=={}
    encrypted=list(tmp_path.glob("*.enc"))
    assert len(encrypted)==1
    ciphertext=encrypted[0].read_bytes()
    assert raw not in ciphertext
    good=FakeCloud()
    receipt=recover_directory(tmp_path,good)
    assert receipt["post_and_media_verified"]==1
    assert receipt["failures"]==0
    assert good.objects["posts/"+pid+"/media/0001.jpg"]==raw


def test_failed_main_run_replays_only_exact_named_artifact(monkeypatch,tmp_path):
    from pathlib import Path
    import json
    import shutil
    import recover_spool_artifacts as mod
    pid=synthetic_post()["id"]
    staged=tmp_path/"encrypted"
    sealed=RecoverySpool(staged).save(pid,first(pid))
    monkeypatch.setenv("GH_TOKEN","synthetic-token-never-sent")
    monkeypatch.setenv("DEMAND_RECOVERY_SOURCE_RUN_ID","123456890")
    def prevent_fuzzy_scan():
        raise AssertionError("must never scan unrelated archives for targeted recovery")
    def fake_gh(args,*,max_bytes=2_000_000):
        if args[0]=="api":
            assert args[1].endswith("/actions/runs/123456890")
            return json.dumps({
                "name":"INTERSECTION — Fast Private Public-Post Capture",
                "head_branch":"main","event":"push",
                "head_repository":{"full_name":"koith/browser-app-lab"}}).encode()
        assert args[:4]==["run","download","123456890","-n"]
        assert args[4]=="intersection-private-recovery"
        target=Path(args[-1])
        assert target.is_dir()
        shutil.copyfile(sealed,target/sealed.name)
        return b""
    monkeypatch.setattr(mod,"list_candidates",prevent_fuzzy_scan)
    monkeypatch.setattr(mod,"_gh",fake_gh)
    cloud=FakeCloud()
    result=mod.replay(cloud=cloud)
    assert result["first_observation_verified"]==1
    assert result["artifact_download_failures"]==0
    assert result["buffer_failures"]==0
    assert cloud.read_first_observation(pid)==canonical_json(first(pid))


def test_replay_circuit_breaker_preserves_deferred_encrypted_buffers(tmp_path,monkeypatch):
    from recover_spool_artifacts import replay
    class UnavailableCloud(FakeCloud):
        def __init__(self):
            super().__init__()
            self.restore_attempts=0
        def save_first_observation(self,*args,**kwargs):
            self.restore_attempts+=1
            raise RuntimeError("synthetic TeraBox write unavailable")
    spool=RecoverySpool(tmp_path)
    for n in range(5):
        pid=hashlib.sha1(str(n).encode()).hexdigest()
        spool.save(pid,first(pid))
    cloud=UnavailableCloud()
    outcome=replay(cloud=cloud,local_directory=tmp_path)
    assert cloud.restore_attempts==3,"provider outage must not stall on every original"
    assert outcome["buffer_failures"]==3
    assert outcome["deferred_buffers"]==2
    assert outcome["encrypted_buffers"]==3
    assert len(list(tmp_path.glob("*.enc")))==5,"deferred ciphertext is never discarded"
    assert cloud.objects=={}


def test_replay_per_record_runner_budget_preserves_exact_original(tmp_path):
    from recover_spool_artifacts import restore_with_budget
    pid=synthetic_post()["id"]
    spool=RecoverySpool(tmp_path)
    sealed=spool.save(pid,first(pid))
    class BoundedCloud(FakeCloud):
        def __init__(self):
            super().__init__()
            self.calls=[]
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            self.calls.append(timeout)
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=BoundedCloud()
    original_runner=cloud.runner
    status=restore_with_budget(spool,sealed,cloud,max_seconds=7)
    assert status=="first_observation_verified"
    assert cloud.calls and all(0<limit<=7 for limit in cloud.calls)
    assert cloud.runner==original_runner
    assert cloud.read_first_observation(pid)==canonical_json(first(pid))
