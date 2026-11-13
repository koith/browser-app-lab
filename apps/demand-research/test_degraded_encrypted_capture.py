"""Synthetic P0 tests for public-original encrypted capture during TeraBox outages."""
from datetime import datetime,timezone

import pytest
import demand_capture_job as job
from demand_archive import post_key,sha256
from test_demand_archive import FakeCloud
from recovery_spool import RecoverySpool,recover_directory


@pytest.fixture(autouse=True)
def private_synthetic_environment(monkeypatch,tmp_path):
    monkeypatch.setenv("DEMAND_ARCHIVE_RECOVERY_KEY","private-synthetic-key-for-failover-tests")
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-terabox-connection-cookie-long")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    monkeypatch.setenv("DEMAND_RECOVERY_SPOOL_DIR",str(tmp_path))
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def source(i):
    oid="at://did:plc:abcdefghijk/app.bsky.feed.post/outage-"+str(i)
    return {"platform":"bluesky","original_id":oid,
            "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/outage-"+str(i),
            "text":"synthetic verified original "+job.TERMS[0],
            "posted_at":"2026-11-03T00:00:00Z",
            "profile_url":"https://bsky.app/profile/did:plc:abcdefghijk",
            "media_urls":["https://cdn.bsky.app/img/real-original-"+str(i)+".jpg"],
            "media_expected":1}


def install_fake_media_fetch(monkeypatch):
    def maker(row,when,get_media=None,pid_override=None,cloud=None):
        pid=pid_override or post_key(row["platform"],row["original_id"])
        raw=("exact synthetic original image "+row["source_url"]).encode()
        p={"id":pid,"platform":row["platform"],"text":row["text"],
           "source_url":row["source_url"],"posted_at":row["posted_at"],
           "captured_at":datetime.fromtimestamp(when,timezone.utc).isoformat(),
           "media_expected":1,"media_saved":1,"archive_complete":True,
           "media":[{"key":"posts/"+pid+"/media/0001.jpg","mime":"image/jpeg",
                     "sha256":sha256(raw),"bytes":len(raw),"remote_verified":True}]}
        return p,[raw]
    monkeypatch.setattr(job,"make_post",maker)


def test_full_cloud_preflight_failure_keeps_five_public_originals_encrypted(tmp_path,monkeypatch):
    class NoPrivateCloud(FakeCloud):
        def preflight(self):
            raise RuntimeError("synthetic private provider unavailable")
        def marker_ids(self):
            raise AssertionError("cannot read remote listing while offline")
    cloud=NoPrivateCloud()
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(5)]
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456935",fast_mode=True)
    encrypted=list(tmp_path.glob("*.enc"))
    assert len(encrypted)==5
    assert cloud.objects=={}
    good=FakeCloud()
    result=recover_directory(tmp_path,good)
    assert result["post_and_media_verified"]==5
    assert result["failures"]==0
    for row in rows:
        pid=post_key(row["platform"],row["original_id"])
        assert good.read_first_observation(pid) is not None
        assert good.objects["posts/"+pid+"/media/0001.jpg"]==(
            "exact synthetic original image "+row["source_url"]).encode()


def test_three_backend_failures_open_circuit_without_stopping_public_observation(tmp_path,monkeypatch):
    class CloudWithFailingWrites(FakeCloud):
        def __init__(self):
            super().__init__()
            self.calls=0
        def save_first_observation(self,*args,**kwargs):
            self.calls+=1
            raise RuntimeError("synthetic remote missing path")
    cloud=CloudWithFailingWrites()
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(6)]
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456936",fast_mode=True)
    assert cloud.calls==3,"after three failures further source reads must not attempt cloud"
    assert len(list(tmp_path.glob("*.enc")))==6
    good=FakeCloud()
    outcome=recover_directory(tmp_path,good)
    assert outcome["post_and_media_verified"]==6
    assert outcome["failures"]==0


def test_buffered_outage_obeys_bounded_public_scan_budget(tmp_path,monkeypatch):
    class Offline(FakeCloud):
        def preflight(self):
            raise RuntimeError("synthetic provider unavailable")
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(30)]
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=Offline(),clock=lambda:1793667900,
                run_id="123456937",fast_mode=True)
    assert len(list(tmp_path.glob("*.enc")))==24



def test_source_first_captures_all_public_originals_without_cloud_calls(tmp_path,monkeypatch):
    """A slow private provider must not block observing fresh public sources."""
    class NeverTouchCloud(FakeCloud):
        def preflight(self):
            raise AssertionError("source-first must never preflight TeraBox")
        def marker_ids(self):
            raise AssertionError("source-first must not block on cloud indexes")
        def write_immutable(self,*args,**kwargs):
            raise AssertionError("source-first must not remotely write each post")
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_DEFER_REMOTE","1")
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(7)]
    cloud=NeverTouchCloud()
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456938",
                fast_mode=True,max_fast_seconds=240)
    assert len(list(tmp_path.glob("*.enc")))==7
    assert cloud.objects=={}
    # The existing recovery consumer, not the fast capture, performs
    # independent immutable post and original-media remote SHA checks.
    restored=recover_directory(tmp_path,FakeCloud())
    assert restored["post_and_media_verified"]==7
    assert restored["failures"]==0


def test_source_first_no_new_data_is_not_a_backup_success(tmp_path,monkeypatch):
    class NeverTouchCloud(FakeCloud):
        def preflight(self):
            raise AssertionError("source-first preflight forbidden")
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_DEFER_REMOTE","1")
    output=job.run(fetchers=[lambda term,start,end:[]],
                   cloud=NeverTouchCloud(),clock=lambda:1793667900,
                   run_id="123456939",fast_mode=True,max_fast_seconds=240)
    assert output["source_first_capture_mode"] is True
    assert output["saved_verified"]==0
    assert output["encrypted_only_originals"]==0
    assert output["operational_status"]=="NO_NEW_PUBLIC_ORIGINALS"
    assert not list(tmp_path.glob("*.enc"))


def test_source_first_preserves_a_sha_verified_encrypted_pack_before_artifact_expiry(tmp_path,monkeypatch):
    """Never label a ciphertext pack as a restored post/media journal entry."""
    import recover_spool_artifacts as replay
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_DEFER_REMOTE","1")
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_PACK_REMOTE","1")
    monkeypatch.setenv("GITHUB_RUN_ID","123456940")
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(3)]
    cloud=FakeCloud()
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456940",
                fast_mode=True,max_fast_seconds=240)
    files=sorted(tmp_path.glob("*.enc"))
    assert len(files)==3
    # One AES-GCM ZIP was independently read back from private cloud, with
    # no raw post, attachment, media URL, or plaintext record stored there.
    keys=list(cloud.objects)
    assert len(keys)==1 and keys[0].startswith("recovery-pack-")
    assert b"synthetic verified original" not in cloud.objects[keys[0]]
    assert not any("posts/" in key for key in keys)
    verified=replay.extract_verified_remote_pack(cloud,keys[0],tmp_path/"verified")
    assert len(verified)==3
    assert all(RecoverySpool(tmp_path).read(p)["first"]["platform"]=="bluesky" for p in verified)
    # Only the separate replay consumer may publish completed post journals.
    assert cloud.load_catalog()==[]


def test_failed_opportunistic_remote_pack_leaves_all_ciphertext_artifacts_untouched(tmp_path,monkeypatch):
    class RejectPack(FakeCloud):
        def write_immutable(self,key,data):
            raise RuntimeError("(authorization) synthetic TeraBox provider denied")
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_DEFER_REMOTE","1")
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_PACK_REMOTE","1")
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(2)]
    cloud=RejectPack()
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456941",
                fast_mode=True,max_fast_seconds=240)
    assert len(list(tmp_path.glob("*.enc")))==2
    assert cloud.objects=={}
    # An independent working remote can still restore those exact bytes.
    restored=recover_directory(tmp_path,FakeCloud())
    assert restored["post_and_media_verified"]==2


def test_source_first_captures_over_24_with_multiple_verified_remote_packs(tmp_path,monkeypatch):
    """36 distinct public originals are not silently dropped at old 24 cap."""
    import recover_spool_artifacts as replay
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_DEFER_REMOTE","1")
    monkeypatch.setenv("DEMAND_FAST_CAPTURE_PACK_REMOTE","1")
    install_fake_media_fetch(monkeypatch)
    rows=[source(i) for i in range(36)]
    cloud=FakeCloud()
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456942",
                fast_mode=True,max_fast_seconds=240)
    sealed=sorted(tmp_path.glob("*.enc"))
    assert len(sealed)==36,"new source-first bound must exceed old 24 cutoff"
    packs=sorted(key for key in cloud.objects if key.startswith("recovery-pack-"))
    assert len(packs)==2,"36 immutable ciphertext originals split 24 + 12"
    verified_count=0
    for i,key in enumerate(packs):
        downloaded=replay.extract_verified_remote_pack(
            cloud,key,tmp_path/("verified-"+str(i)))
        assert all(RecoverySpool(tmp_path).read(f)["first"]["platform"]=="bluesky"
                   for f in downloaded)
        verified_count+=len(downloaded)
    assert verified_count==36
    # Only sealed originals are copied; no post/media journal is presented as
    # individually remotely verified until the separate strict replay succeeds.
    assert cloud.load_catalog()==[]
    assert not any(key.startswith("posts/") for key in cloud.objects)
