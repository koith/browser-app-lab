"""Synthetic, credential-free acceptance tests for immutable public captures.

The TeraBox nested directory for a newly observed post sometimes rejects
uploads. The flat metadata fallback must preserve exactly the same post bytes.
"""
import json

import pytest
from demand_archive import canonical_json, post_key
from test_demand_archive import FakeCloud
import demand_capture_job as job


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


class UnavailableNestedCapture(FakeCloud):
    def __init__(self):
        super().__init__()
        self.nested_failures=0

    def fake(self,args,data=None,timeout=150,allow_missing=False):
        if args[0] in ("copyto","rcat"):
            target=args[2] if args[0]=="copyto" else args[1]
            if target.endswith("/capture.json") and "/posts/" in target:
                self.nested_failures+=1
                raise RuntimeError("private cloud upload failed (missing)")
        return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)


def first_payload(pid,observed=1793667600):
    return {
      "id":pid, "platform":"bluesky", "text":"synthetic permitted public observation",
      "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/first",
      "posted_at":"2026-11-03T00:00:00Z", "observed_at":observed,
      "media_links":[], "profile_url":"https://bsky.app/profile/did:plc:abcdefghijk",
    }


def test_flat_metadata_fallback_is_sha_verified_when_new_post_folder_upload_fails():
    cloud=UnavailableNestedCapture()
    pid=post_key("bluesky","at://did:plc:abcdefghijk/app.bsky.feed.post/first")
    raw=canonical_json(first_payload(pid))
    assert cloud.save_first_observation(pid,raw)==raw
    canonical,flat=cloud.first_observation_keys(pid)
    assert canonical not in cloud.objects
    assert cloud.objects[flat]==raw
    assert cloud.read_first_observation(pid)==raw
    assert cloud.nested_failures>0


def test_flat_fallback_is_immutable_and_first_observation_wins():
    cloud=UnavailableNestedCapture()
    pid="a"*40
    earlier=canonical_json(first_payload(pid))
    later=canonical_json(first_payload(pid,1793667900))
    assert cloud.save_first_observation(pid,earlier)==earlier
    assert cloud.save_first_observation(pid,later)==earlier
    assert cloud.objects[cloud.first_observation_keys(pid)[1]]==earlier
    assert len([k for k in cloud.objects if k.startswith("metadata/early-")])==1


def test_flat_orphan_found_without_post_dir_and_recovered_after_public_source_gone(monkeypatch):
    cloud=UnavailableNestedCapture()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    original_id="at://did:plc:abcdefghijk/app.bsky.feed.post/first"
    pid=post_key("bluesky",original_id)
    raw=canonical_json(first_payload(pid))
    cloud.save_first_observation(pid,raw)
    assert pid in cloud.pending_capture_ids({})
    outcome=job.run(
      fetchers=[lambda term,start,end: []],
      cloud=cloud,clock=lambda:1793668200,run_id="123456779",fast_mode=False)
    assert outcome["recovered_early_snapshots"]==1
    assert outcome["storage_failures"]==0
    assert cloud.load_catalog()[0]["id"]==pid
    assert cloud.read_first_observation(pid)==raw


def test_invalid_flat_first_observation_is_quarantined_not_published(monkeypatch):
    cloud=UnavailableNestedCapture()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    pid="b"*40
    cloud.objects[cloud.first_observation_keys(pid)[1]]=b'{"id":"wrong"}'
    outcome=job.run(
      fetchers=[lambda term,start,end:[]],
      cloud=cloud,clock=lambda:1793668200,run_id="123456780",fast_mode=False)
    assert outcome["invalid_early_captures"]==1
    assert pid not in [x["id"] for x in cloud.load_catalog()]
    assert cloud.objects[cloud.first_observation_keys(pid)[1]]==b'{"id":"wrong"}'


def test_fast_capture_prioritizes_flat_observation_before_nested_storage(monkeypatch):
    cloud=UnavailableNestedCapture()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    original_id="at://did:plc:abcdefghijk/app.bsky.feed.post/first"
    pid=post_key("bluesky",original_id)
    row={"platform":"bluesky","original_id":original_id,
         "source_url":first_payload(pid)["source_url"],
         "profile_url":first_payload(pid)["profile_url"],
         "posted_at":first_payload(pid)["posted_at"],
         "text":first_payload(pid)["text"],"media_urls":[],"media_expected":0}
    outcome=job.run(fetchers=[
         lambda term,start,end:[row] if term==job.TERMS[0] else []],
         cloud=cloud,clock=lambda:1793668200,
         run_id="123456781",fast_mode=True)
    assert outcome["saved_verified"]==1
    assert outcome["storage_failures"]==0
    assert cloud.nested_failures==0,"flat snapshot must precede nested capture writes"
    canonical,flat=cloud.first_observation_keys(pid)
    assert canonical not in cloud.objects
    assert flat in cloud.objects
    assert cloud.load_catalog()[0]["id"]==pid


def test_first_observation_fails_closed_if_both_remote_paths_reject_writes():
    class BothPathsUnavailable(UnavailableNestedCapture):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0] in ("copyto","rcat"):
                target=args[2] if args[0]=="copyto" else args[1]
                if "/capture.json" in target or "/early-" in target:
                    raise RuntimeError("private cloud upload failed (missing)")
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=BothPathsUnavailable()
    pid="c"*40
    raw=canonical_json(first_payload(pid))
    with pytest.raises(RuntimeError,match="first observation unavailable"):
        cloud.save_first_observation(pid,raw,prefer_flat=True)
    assert cloud.read_first_observation(pid) is None
    assert not any("early-"+pid in k for k in cloud.objects)
