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
