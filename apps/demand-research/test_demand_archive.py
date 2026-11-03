"""Offline acceptance checks for immutable, prompt, private capture (no credentials)."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from demand_archive import CloudArchive, canonical_json, post_key, sha256
import demand_capture_job as job


class FakeCloud(CloudArchive):
    def __init__(self):
        self.objects = {}
        super().__init__(remote="archive:DemandResearch", runner=self.fake)

    def fake(self, args, data=None, timeout=150, allow_missing=False):
        op = args[0]
        if op == "lsf":
            if "--dirs-only" in args and args[1].endswith("/posts"):
                found = sorted({k.split("/")[1] + "/" for k in self.objects
                                if k.startswith("posts/") and len(k.split("/")) >= 3})
                return ("\n".join(found) + ("\n" if found else "")).encode()
            if args[1] == "archive:":
                return b"DemandResearch/\n"
            prefix = args[1].split("archive:DemandResearch/", 1)[1].rstrip("/") + "/"
            found = [k[len(prefix):] for k in self.objects if k.startswith(prefix)
                     and "/" not in k[len(prefix):]]
            return ("\n".join(sorted(found)) + ("\n" if found else "")).encode()
        if op == "cat":
            key = args[1].split("archive:DemandResearch/", 1)[1]
            if key not in self.objects:
                if allow_missing:
                    return None
                raise RuntimeError("missing mock cloud file")
            return self.objects[key]
        if op == "rcat":
            key = args[1].split("archive:DemandResearch/", 1)[1]
            self.objects[key] = data
            return b""
        if op == "copyto":
            key = args[2].split("archive:DemandResearch/", 1)[1]
            self.objects[key] = Path(args[1]).read_bytes()
            return b""
        raise AssertionError("unrecognized remote operation")


def post():
    return {
        "id": post_key("bluesky", "at://did:plc:abcdefghijk/app.bsky.feed.post/abc"),
        "platform": "bluesky",
        "text": "approved synthetic consumer test",
        "source_url": "https://bsky.app/profile/did:plc:abcdefghijk/post/abc",
        "posted_at": "2026-11-03T00:00:00+00:00",
        "captured_at": "2026-11-03T00:01:00+00:00",
        "media": [], "media_expected": 0, "media_saved": 0,
        "archive_complete": True,
    }


def test_new_and_legacy_catalog_preserved(monkeypatch):
    cloud = FakeCloud()
    cloud.objects["metadata/catalog.json"] = canonical_json({
        "schema_version": 1, "posts": [{
            **post(), "id": "a" * 40, "source_url": "https://bsky.app/profile/a/post/legacy"
        }]})
    old = cloud.load_catalog()
    assert len(old) == 1
    p = post()
    cloud.save_post(p)
    recovered, num = cloud.recover_entries({x["id"]: x for x in old})
    assert num == 1 and len(recovered) == 2
    info = cloud.publish_catalog(recovered, "123456789")
    assert info["posts"] == 2
    assert len(cloud.load_catalog()) == 2
    assert len(json.loads(cloud.objects["metadata/catalog.json"])["posts"]) == 1
    cloud.save_post(p)  # duplicate is byte-identical; no loss or overwrite
    with pytest.raises(RuntimeError, match="immutable"):
        cloud.write_immutable("posts/" + p["id"] + "/post.json", b"tampered")


def test_mid_run_crash_recovered_by_entry_markers():
    cloud = FakeCloud()
    p = post()
    cloud.save_post(p)
    assert cloud.load_catalog() == []  # pointer was never published
    recovered, count = cloud.recover_entries({})
    assert count == 1 and recovered[p["id"]] == p
    cloud.publish_catalog(recovered, "123456790")
    assert cloud.load_catalog() == [p]


def test_remote_corruption_blocks_recovery():
    cloud = FakeCloud()
    p = post()
    cloud.save_post(p)
    cloud.objects["posts/" + p["id"] + "/post.json"] = b"unexpected bad bytes"
    recovered, count = cloud.recover_entries({})
    assert count == 0 and recovered == {}
    assert cloud.unrecoverable_entries == 1
    assert p["id"] in cloud.quarantined_ids
    assert p["id"] not in cloud.pending_capture_ids({})
    assert cloud.objects["metadata/entries/" + p["id"] + ".json"]


def test_media_sha_and_remote_readback():
    cloud = FakeCloud()
    p = post()
    raw = b"\x89PNG\r\n\x1a\nVALID SYNTHETIC BYTES"
    p["media"] = [{"key": "posts/" + p["id"] + "/media/0001.png",
                   "mime": "image/png", "bytes": len(raw),
                   "sha256": sha256(raw), "remote_verified": True}]
    cloud.save_post(p, [raw])
    assert cloud.objects[p["media"][0]["key"]] == raw
    with pytest.raises(ValueError, match="bad original"):
        cloud.save_post({**p, "id": "a"*40,
                         "media": [{**p["media"][0], "key": "posts/" + "a"*40 + "/media/0001.png"}]},
                        [b"wrong"])


def test_current_public_source_and_partial_media(monkeypatch):
    now = 1793667600
    start = now - 900
    body = {
      "posts": [
        {"uri": "at://did:plc:abcdefghijk/app.bsky.feed.post/abcdef",
         "author": {"did": "did:plc:abcdefghijk"},
         "record": {"text": "섹트 상품 후기", "createdAt": "2026-11-03T00:55:00Z"},
         "embed": {"images": [{"fullsize": "https://cdn.bsky.app/img/something.jpg"}]}},
        {"uri": "at://did:plc:abcdefghijk/app.bsky.feed.post/restricted",
         "author": {"did": "did:plc:abcdefghijk"},
         "record": {"text": "섹트 private", "createdAt": "2026-11-03T00:55:00Z"},
         "labels": [{"val": "!hide"}]}
      ]
    }
    monkeypatch.setattr(job, "bluesky_public_search", lambda *args: body)
    matches = list(job.bluesky("섹트", start, now))
    assert len(matches) == 1
    assert matches[0]["media_expected"] == 1
    p, blobs = job.make_post(matches[0], now, get_media=lambda url: None)
    assert p["archive_complete"] is False
    assert p["media_saved"] == 0 and blobs == []
    assert not job.media_allowed("http://cdn.bsky.app/img/unsafe")
    assert not job.media_allowed("https://169.254.169.254/latest/meta-data")
    assert not job.media_allowed("https://cdn.bsky.app.evil.net/x")


def test_job_persists_text_before_media_and_public_catalog(monkeypatch):
    cloud = FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE", "offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED", "1")
    row = {
        "platform": "bluesky",
        "original_id": "at://did:plc:abcdefghijk/app.bsky.feed.post/test01",
        "source_url": "https://bsky.app/profile/did:plc:abcdefghijk/post/test01",
        "text": "섹트 test only",
        "posted_at": "2026-11-03T00:00:00Z",
        "media_urls": [], "media_expected": 0,
    }
    result = job.run(fetchers=[lambda term, start, end:
        [row] if term == "섹트" else []], cloud=cloud,
        clock=lambda: 1793667600, run_id="123456791")
    assert result["saved_verified"] == 1
    assert result["catalog"]["posts"] == 1
    pid = post_key("bluesky", row["original_id"])
    assert "posts/" + pid + "/capture.json" in cloud.objects
    assert "metadata/entries/" + pid + ".json" in cloud.objects
    assert cloud.load_catalog()[0]["id"] == pid
    assert job.run(fetchers=[lambda term, start, end:
        [row] if term == "섹트" else []], cloud=cloud,
        clock=lambda: 1793667900, run_id="123456792")["saved_verified"] == 0


def test_disabled_capture_fails_closed(monkeypatch):
    monkeypatch.delenv("DEMAND_CAPTURE_PUBLIC_ALLOWED", raising=False)
    with pytest.raises(RuntimeError, match="authorization"):
        job.run(fetchers=[lambda *args: []], cloud=FakeCloud(),
                run_id="123456793")


def test_orphan_first_observation_recovered_even_after_source_disappears(monkeypatch):
    cloud = FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE", "offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED", "1")
    pid = post_key("bluesky", "at://did:plc:abcdefghijk/app.bsky.feed.post/suddenlydeleted")
    first = {"id": pid, "platform": "bluesky", "text": "섹트 first observation",
             "source_url": "https://bsky.app/profile/did:plc:abcdefghijk/post/suddenlydeleted",
             "posted_at": "2026-11-03T00:00:00Z",
             "profile_url": "https://bsky.app/profile/did:plc:abcdefghijk",
             "observed_at": 1793667600, "media_links": []}
    cloud.write_immutable("posts/" + pid + "/capture.json", canonical_json(first))
    assert cloud.load_catalog() == []
    result = job.run(fetchers=[lambda *args: []], cloud=cloud,
                     clock=lambda: 1793667900, run_id="123456794")
    assert result["saved_verified"] == 0
    assert result["recovered_early_snapshots"] == 1
    assert cloud.load_catalog()[0]["text"] == "섹트 first observation"
    assert cloud.load_catalog()[0]["captured_at"] == "2026-11-03T01:00:00+00:00"


def test_transient_copyto_rejection_falls_back_to_rcat_and_readback():
    class AlternateCloud(FakeCloud):
        def __init__(self):
            super().__init__()
            self.copy_failures = 0

        def fake(self, args, data=None, timeout=150, allow_missing=False):
            if args[0] == "copyto" and self.copy_failures == 0:
                self.copy_failures += 1
                raise RuntimeError("private cloud copyto failed (backend_rejected)")
            return super().fake(args, data=data, timeout=timeout,
                                allow_missing=allow_missing)

    cloud = AlternateCloud()
    p = post()
    cloud.save_post(p)
    assert cloud.copy_failures == 1
    assert json.loads(cloud.objects["posts/" + p["id"] + "/post.json"]) == p


def test_permission_error_does_not_masquerade_as_missing_remote(monkeypatch):
    from demand_archive import CloudArchive
    class Result:
        returncode = 3
        stderr = b"error 403 permission denied"
        stdout = b""
    monkeypatch.setattr("demand_archive.subprocess.run", lambda *a, **k: Result())
    with pytest.raises(RuntimeError, match="authorization"):
        CloudArchive._run(["cat", "archive:DemandResearch/file"], allow_missing=True)


def test_prior_immutable_post_survives_different_observation_time():
    cloud = FakeCloud()
    first = post()
    cloud.save_post(first)
    later = {**first, "captured_at": "2026-11-03T02:00:00+00:00"}
    chosen = cloud.save_post(later)
    assert chosen == first
    assert json.loads(cloud.objects["posts/" + first["id"] + "/post.json"]) == first
    assert cloud.recover_entries({})[0][first["id"]] == first


def test_readback_race_preserves_original_first_observation(monkeypatch):
    class StaleReadCloud(FakeCloud):
        def __init__(self):
            super().__init__()
            self.missing_once = False
            self.conflict_once = True

        def pending_capture_ids(self, existing):
            return []

        def read(self, key, *, cap=70_000_000, optional=False):
            if key.endswith("/capture.json") and not self.missing_once:
                self.missing_once = True
                return None
            return super().read(key, cap=cap, optional=optional)

        def write_immutable(self, key, data):
            if key.endswith("/capture.json") and self.conflict_once:
                self.conflict_once = False
                raise RuntimeError("immutable cloud write collision/readback mismatch")
            return super().write_immutable(key, data)

    cloud = StaleReadCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE", "offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED", "1")
    original_id = "at://did:plc:abcdefghijk/app.bsky.feed.post/stale01"
    pid = post_key("bluesky", original_id)
    early = {"id": pid, "platform": "bluesky",
             "text": "뒷계 합성 데이터 최초 본문",
             "source_url": "https://bsky.app/profile/did:plc:abcdefghijk/post/stale01",
             "posted_at": "2026-11-03T00:00:00Z",
             "observed_at": 1793667600, "media_links": []}
    cloud.objects["posts/" + pid + "/capture.json"] = canonical_json(early)
    row = {"platform": "bluesky", "original_id": original_id,
           "source_url": early["source_url"], "text": early["text"],
           "posted_at": early["posted_at"], "media_urls": [],
           "media_expected": 0}
    result = job.run(fetchers=[lambda term, start, end:
        [row] if term == "뒷계" else []], cloud=cloud,
        clock=lambda: 1793667900, run_id="123456795")
    assert result["saved_verified"] == 1
    assert result["catalog"]["posts"] == 1
    assert cloud.load_catalog()[0]["text"] == early["text"]


def test_corrupted_legacy_entry_recovered_without_deleting_original():
    cloud = FakeCloud()
    original = post()
    cloud.save_post(original)
    key = "metadata/entries/" + original["id"] + ".json"
    cloud.objects[key] = b'{"id":"bad","sha256":"broken"}'
    restored, count = cloud.recover_entries({})
    assert count == 1 and restored[original["id"]] == original
    assert cloud.repaired_entries == 1
    assert cloud.objects[key] == b'{"id":"bad","sha256":"broken"}'
    backup = "metadata/entries-repaired/" + original["id"] + ".json"
    assert json.loads(cloud.objects[backup])["id"] == original["id"]
    assert cloud.recover_entries({})[0][original["id"]] == original
    assert cloud.repaired_entries == 0


def test_invalid_marker_without_post_is_quarantined_not_catalogued():
    cloud = FakeCloud()
    pid = "b"*40
    cloud.objects["metadata/entries/" + pid + ".json"] = b"not JSON"
    restored, count = cloud.recover_entries({})
    assert count == 0 and restored == {}
    assert cloud.unrecoverable_entries == 1
    assert "metadata/entries-repaired/" + pid + ".json" not in cloud.objects


def test_existing_invalid_marker_uses_separate_repaired_namespace():
    cloud = FakeCloud()
    original = post()
    key = "metadata/entries/" + original["id"] + ".json"
    cloud.objects[key] = b"corrupt"
    saved = cloud.save_post(original)
    assert saved == original
    assert cloud.objects[key] == b"corrupt"
    restored, count = cloud.recover_entries({})
    assert count == 1 and restored[original["id"]] == original


def test_corrupt_record_does_not_block_other_verified_posts(monkeypatch):
    cloud = FakeCloud()
    old = post()
    cloud.save_post(old)
    cloud.objects["posts/" + old["id"] + "/post.json"] = b"bad old bytes"
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE", "offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED", "1")
    row = {
        "platform": "bluesky",
        "original_id": "at://did:plc:abcdefghijk/app.bsky.feed.post/newgood01",
        "source_url": "https://bsky.app/profile/did:plc:abcdefghijk/post/newgood01",
        "text": "synthetic test " + job.TERMS[0],
        "posted_at": "2026-11-03T00:00:00Z",
        "media_urls": [], "media_expected": 0,
    }
    result=job.run(fetchers=[lambda term, start, end: [row] if term==job.TERMS[0] else []],
                   cloud=cloud,clock=lambda:1793667900,run_id="123456799")
    assert result["saved_verified"] == 1
    assert result["unrecoverable_markers"] == 1
    assert cloud.load_catalog()[0]["id"]==post_key("bluesky",row["original_id"])
    assert cloud.objects["posts/" + old["id"] + "/post.json"] == b"bad old bytes"


def test_capture_budget_keeps_catalog_and_reports_partial_coverage(monkeypatch):
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    monkeypatch.setattr(job,"MAX_PER_RUN",1)
    rows=[{
        "platform":"bluesky",
        "original_id":"at://did:plc:abcdefghijk/app.bsky.feed.post/budget"+str(i),
        "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/budget"+str(i),
        "text":"synthetic allowed record "+job.TERMS[0],
        "posted_at":"2026-11-03T00:00:00Z",
        "media_urls":[],"media_expected":0
    } for i in range(2)]
    result=job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                   cloud=cloud,clock=lambda:1793667900,run_id="123456812")
    assert result["saved_verified"]==1
    assert result["budget_exhausted"] is True
    assert result["completeness_guaranteed"] is False
    assert len(cloud.load_catalog())==1


def test_one_cloud_write_failure_does_not_block_other_verified_catalogued_record(monkeypatch):
    class FailingCloud(FakeCloud):
        def __init__(self):
            super().__init__()
            self.failed_once = False

        def write_immutable(self, key, data):
            if key.endswith("/capture.json") and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("test-only remote write unavailable")
            return super().write_immutable(key, data)

    cloud=FailingCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    rows=[{
        "platform":"bluesky",
        "original_id":"at://did:plc:abcdefghijk/app.bsky.feed.post/transient"+str(i),
        "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/transient"+str(i),
        "text":"synthetic public "+job.TERMS[0],
        "posted_at":"2026-11-03T00:00:00Z",
        "media_urls":[],"media_expected":0
    } for i in range(2)]
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=cloud,clock=lambda:1793667900,run_id="123456813")
    assert cloud.failed_once
    assert len(cloud.load_catalog())==1,"successful record must be published despite another failure"
    assert cloud.load_catalog()[0]["id"]==post_key("bluesky",rows[1]["original_id"])
