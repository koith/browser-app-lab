"""Offline acceptance checks for immutable, prompt, private capture (no credentials)."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from demand_archive import CloudArchive, canonical_json, post_key, sha256
import demand_capture_job as job

@pytest.fixture(autouse=True)
def no_real_backoff_in_isolated_archive_tests(monkeypatch):
    # Exercise retry branches without wasting CI wall-clock on artificial sleeps.
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)



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
        if op == "mkdir":
            return b""
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
    assert cloud.load_catalog(include_entries=False)==[],"pointer was never published"
    assert cloud.load_catalog()==[p],"verified entry journal is independently readable"
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


def test_eventually_consistent_remote_recovers_from_two_stale_reads(monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    class StaleCloud(FakeCloud):
        def __init__(self):
            super().__init__()
            self.stale_remaining = 0

        def fake(self, args, data=None, timeout=150, allow_missing=False):
            if args[0] in ("copyto","rcat"):
                result=super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)
                self.stale_remaining=2
                return result
            if args[0]=="cat" and self.stale_remaining>0:
                self.stale_remaining-=1
                return b"synthetic stale remote bytes"
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)

    cloud=StaleCloud()
    p=post()
    cloud.save_post(p)
    assert cloud.stale_remaining==0
    assert json.loads(cloud.objects["posts/"+p["id"]+"/post.json"])==p
    assert cloud.recover_entries({})[0][p["id"]]==p


def test_existing_conflicting_remote_bytes_never_overwritten(monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    cloud=FakeCloud()
    target="posts/"+"a"*40+"/post.json"
    cloud.objects[target]=b"synthetic existing content"
    with pytest.raises(RuntimeError,match="immutable"):
        cloud.write_immutable(target,b"new synthetic bytes")
    assert cloud.objects[target]==b"synthetic existing content"


def test_parent_missing_triggers_safe_mkdir_then_alternate_method(monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    class ParentMissing(FakeCloud):
        def __init__(self):
            super().__init__()
            self.failed=False
            self.mkdir_count=0

        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="copyto" and not self.failed:
                self.failed=True
                raise RuntimeError("private cloud copyto failed (missing)")
            if args[0]=="mkdir":
                self.mkdir_count+=1
                return b""
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)

    cloud=ParentMissing()
    p=post()
    cloud.save_post(p)
    assert cloud.failed and cloud.mkdir_count>=1
    assert cloud.objects["posts/"+p["id"]+"/post.json"]==canonical_json(p)


def test_nested_catalog_parent_bootstrap_before_first_cloud_upload():
    class NestedDirectoryBackend(FakeCloud):
        def __init__(self):
            super().__init__()
            self.directories={"", "DemandResearch"}
            self.mkdir_order=[]

        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="mkdir":
                dst=args[1].split("archive:",1)[1].strip("/")
                parent=dst.rsplit("/",1)[0] if "/" in dst else ""
                if parent not in self.directories:
                    raise RuntimeError("private cloud mkdir failed (missing)")
                self.directories.add(dst)
                self.mkdir_order.append(dst)
                return b""
            if args[0] in ("copyto","rcat"):
                dst=args[2] if args[0]=="copyto" else args[1]
                parent=dst.split("archive:",1)[1].rsplit("/",1)[0].strip("/")
                if parent not in self.directories:
                    raise RuntimeError("private cloud "+args[0]+" failed (missing)")
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)

    cloud=NestedDirectoryBackend()
    p=post()
    cloud.save_post(p)
    catalog=cloud.publish_catalog({p["id"]:p},"123456901")
    assert catalog["catalog_sha256_verified"] is True
    assert cloud.load_catalog()[0]["id"]==p["id"]
    assert "DemandResearch/metadata" in cloud.mkdir_order
    assert "DemandResearch/metadata/catalogs" in cloud.mkdir_order
    assert "DemandResearch/metadata/manifests" in cloud.mkdir_order
    assert cloud.mkdir_order.index("DemandResearch/metadata")<cloud.mkdir_order.index("DemandResearch/metadata/catalogs")


def test_parent_mkdir_failure_prevents_false_storage_success():
    class NoParentPermission(FakeCloud):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="mkdir":
                raise RuntimeError("private cloud mkdir failed (authorization)")
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)

    cloud=NoParentPermission()
    with pytest.raises(RuntimeError,match="authorization"):
        cloud.save_post(post())
    assert not any(key.endswith("/post.json") for key in cloud.objects)


def test_read_only_archive_summary_reports_remote_sample_without_mutation(monkeypatch):
    from inspect_terabox_status import inspect
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    p=post()
    cloud.save_post(p)
    cloud.publish_catalog({p["id"]:p},"123456987")
    before=dict(cloud.objects)
    status=inspect(cloud)
    assert status["catalog_post_count"]==1
    assert status["catalog_expected_bytes"]>0
    assert status["versioned_manifest_count"]==1
    assert status["entry_marker_count"]==1
    assert status["sample_valid"]==1
    assert status["sample_mismatch"]==0
    assert cloud.objects==before,"audit must never mutate archive"


def test_malformed_early_capture_is_isolated_without_poisoning_good_recovery(monkeypatch):
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    bad_id="d"*40
    cloud.objects["posts/"+bad_id+"/capture.json"]=b'{"incomplete":true}'
    original_id="at://did:plc:abcdefghijk/app.bsky.feed.post/goodrestored01"
    pid=post_key("bluesky",original_id)
    early={
        "id":pid,"platform":"bluesky","text":"synthetic "+job.TERMS[0],
        "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/goodrestored01",
        "posted_at":"2026-11-03T00:00:00Z","observed_at":1793667600,
        "media_links":[]
    }
    cloud.objects["posts/"+pid+"/capture.json"]=canonical_json(early)
    status=job.run(fetchers=[lambda *args:[]],cloud=cloud,
                   clock=lambda:1793667900,run_id="123456945")
    assert status["invalid_early_captures"]==1
    assert status["recovered_early_snapshots"]==1
    assert status["catalog"]["posts"]==1
    assert cloud.load_catalog()[0]["id"]==pid
    assert cloud.objects["posts/"+bad_id+"/capture.json"]==b'{"incomplete":true}'
    assert bad_id in cloud.quarantined_ids
    assert not any(key.startswith("posts/"+bad_id+"/post.json") for key in cloud.objects)


def test_compact_catalog_does_not_duplicate_original_text_or_media():
    cloud=FakeCloud()
    p=post()
    p["text"]="SYNTHETIC PRIVATE TEST BODY SHOULD NOT ENTER INDEX"
    cloud.save_post(p)
    info=cloud.publish_catalog({p["id"]:p},"123456991")
    assert info["index_format"]=="sha256_references_only"
    index=cloud.objects["metadata/catalogs/catalog-123456991.json"]
    parsed=json.loads(index)
    assert parsed["schema_version"]==2
    assert parsed["post_refs"]==[{"id":p["id"],"sha256":sha256(canonical_json(p))}]
    assert p["text"].encode() not in index
    assert cloud.load_catalog()==[p]


def test_failed_compact_catalog_publication_keeps_verified_journal_readable(monkeypatch):
    class CatalogDenied(FakeCloud):
        def write_immutable(self,key,data):
            if key.startswith("metadata/catalogs/"):
                raise RuntimeError("synthetic backend refused catalog")
            return super().write_immutable(key,data)

    cloud=CatalogDenied()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    row={
        "platform":"bluesky",
        "original_id":"at://did:plc:abcdefghijk/app.bsky.feed.post/journal01",
        "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/journal01",
        "text":"synthetic "+job.TERMS[0],
        "posted_at":"2026-11-03T00:00:00Z",
        "media_urls":[],"media_expected":0
    }
    result=job.run(fetchers=[lambda term,start,end:[row] if term==job.TERMS[0] else []],
                   cloud=cloud,clock=lambda:1793667900,run_id="123456992")
    assert result["saved_verified"]==1
    assert result["catalog"]["catalog_sha256_verified"] is False
    assert result["catalog"]["publication_pending"] is True
    assert result["operational_status"]=="DEGRADED_INDEX"
    assert len(cloud.load_catalog(include_entries=False))==0
    assert len(cloud.load_catalog())==1
    assert cloud.load_catalog()[0]["id"]==post_key("bluesky",row["original_id"])


def test_fast_capture_only_checks_marker_names_and_saves_new_post(monkeypatch):
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    first=post()
    cloud.save_post(first)
    old_id="at://did:plc:abcdefghijk/app.bsky.feed.post/abc"
    rows=[
        {"platform":"bluesky","original_id":original,"source_url":
         "https://bsky.app/profile/did:plc:abcdefghijk/post/"+suffix,
         "text":"synthetic only "+job.TERMS[0],
         "posted_at":"2026-11-03T00:00:00Z","media_urls":[],"media_expected":0}
        for original,suffix in [
          (old_id,"abc"),
          ("at://did:plc:abcdefghijk/app.bsky.feed.post/newfast01","newfast01")]
    ]
    class FastCloud(FakeCloud):
        def load_catalog(self,*args,**kwargs):
            raise AssertionError("fast poll must not download old post journal")
        def recover_entries(self,*args,**kwargs):
            raise AssertionError("fast poll must not verify old post hashes")
        def pending_capture_ids(self,*args,**kwargs):
            raise AssertionError("fast poll must not scan old captures")

    fast=FastCloud()
    fast.objects=cloud.objects
    result=job.run(
        fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
        cloud=fast, clock=lambda:1793667900,
        run_id="123456996", fast_mode=True)
    assert result["saved_verified"]==1
    assert result["duplicates"]==1
    assert result["operational_status"]=="JOURNAL_ONLY"
    assert result["storage_failures"]==0
    assert not any("metadata/manifests/" in key for key in cloud.objects)
    assert len(CloudArchive(remote=fast.remote,runner=fast.runner)
               .load_catalog(include_entries=True))==2


def test_separate_repair_reconciles_fast_journal_and_publishes_compact_index(monkeypatch):
    from rebuild_archive import rebuild
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    cloud.save_post(post())
    summary=rebuild(cloud,run_id="123456997")
    assert summary["catalog_matches_journal"] is True
    assert summary["journal_readable_posts"]==1
    assert summary["published_catalog_posts"]==1
    assert summary["catalog_published_this_run"] is True
    assert len(cloud.load_catalog(include_entries=False))==1
    versions=[k for k in cloud.objects if k.startswith("metadata/catalogs/")]
    assert len(versions)==1
    compact=json.loads(cloud.objects[versions[0]])
    assert compact["schema_version"]==2
    assert "text" not in json.dumps(compact)
    assert "post_refs" in compact


def test_checksum_mismatch_can_be_repaired_only_with_matching_first_capture(monkeypatch):
    from datetime import datetime
    cloud=FakeCloud()
    p=post()
    cloud.save_post(p)
    pid=p["id"]
    new={**p,"profile_url":"https://bsky.app/profile/did:plc:abcdefghijk"}
    newer=canonical_json(new)
    cloud.objects["posts/"+pid+"/post.json"]=newer
    first={"id":pid,"platform":p["platform"],"source_url":p["source_url"],
           "posted_at":p["posted_at"],"text":p["text"],"media_links":[],
           "observed_at":int(datetime.fromisoformat(p["captured_at"]).timestamp())}
    cloud.objects["posts/"+pid+"/capture.json"]=canonical_json(first)
    old_marker=cloud.objects["metadata/entries/"+pid+".json"]
    found,count=cloud.recover_entries({})
    assert count==1 and found[pid]==new
    assert cloud.repaired_entries==1
    assert cloud.unrecoverable_entries==0
    assert cloud.objects["metadata/entries/"+pid+".json"]==old_marker
    repair="metadata/entries-repaired/"+pid+".json"
    assert json.loads(cloud.objects[repair])["sha256"]==sha256(newer)
    assert cloud.recover_entries({},repair=False)[0][pid]==new


def test_conflicting_first_capture_is_never_silently_resigned():
    from datetime import datetime
    cloud=FakeCloud()
    p=post()
    cloud.save_post(p)
    pid=p["id"]
    changed={**p,"text":"different unverified text"}
    cloud.objects["posts/"+pid+"/post.json"]=canonical_json(changed)
    first={"id":pid,"platform":p["platform"],"source_url":p["source_url"],
           "posted_at":p["posted_at"],"text":p["text"],"media_links":[],
           "observed_at":int(datetime.fromisoformat(p["captured_at"]).timestamp())}
    cloud.objects["posts/"+pid+"/capture.json"]=canonical_json(first)
    recovered,count=cloud.recover_entries({})
    assert not recovered and count==0
    assert cloud.unrecoverable_entries==1
    assert pid in cloud.quarantined_ids
    assert "metadata/entries-repaired/"+pid+".json" not in cloud.objects


def test_safe_storage_error_classification_never_reflects_user_post_or_url():
    from demand_capture_job import public_error_class
    assert public_error_class(RuntimeError("private cloud rcat failed (rate_limited)"))=="backend_rate_limit"
    assert public_error_class(RuntimeError("private cloud readback did not converge"))=="readback_mismatch"
    assert public_error_class(ValueError("early original capture mismatch; cannot silently replace"))=="first_observation_conflict"
    assert public_error_class(ValueError("secret person https://example.com/p/42"))=="unclassified_failure"


def test_verified_v2_catalog_reads_through_transient_wrong_post_bytes():
    class StalePost(FakeCloud):
        def __init__(self):
            super().__init__()
            self.stale_remaining=0
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if (args[0]=="cat" and args[1].endswith("/post.json")
                    and self.stale_remaining>0):
                self.stale_remaining-=1
                return b"transient stale bytes not matching SHA256"
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)

    cloud=StalePost()
    p=post()
    cloud.save_post(p)
    cloud.publish_catalog({p["id"]:p},"123456963")
    cloud.stale_remaining=2
    rows=cloud.load_catalog(include_entries=False)
    assert len(rows)==1 and rows[0]["id"]==p["id"]
    assert cloud.catalog_unverified_refs==0
    assert cloud.stale_remaining==0


def test_compact_index_accepts_concurrent_appended_verified_post(monkeypatch):
    from rebuild_archive import rebuild
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")
    first=post()
    cloud.save_post(first)
    later={**first,"id":"b"*40,
           "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/other",
           "text":"second verified synthetic observation"}
    publish=cloud.publish_catalog
    def with_concurrent_upload(*args,**kwargs):
        result=publish(*args,**kwargs)
        cloud.save_post(later)
        return result
    cloud.publish_catalog=with_concurrent_upload
    outcome=rebuild(cloud,run_id="123456964")
    assert outcome["snapshot_sha_verified"] is True
    assert outcome["catalog_matches_journal"] is False
    assert outcome["index_lag_post_count"]==1
    assert outcome["fully_reconciled"] is False
    assert len(cloud.load_catalog(include_entries=True))==2


def test_read_only_audit_waits_for_matching_remote_post_checksum(monkeypatch):
    from inspect_terabox_status import inspect
    cloud=FakeCloud()
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test")
    p=post()
    cloud.save_post(p)
    cloud.publish_catalog({p["id"]:p},"123456965")
    original=cloud.fake
    stale={"remaining":2}
    def temporary_old_post(args,data=None,timeout=150,allow_missing=False):
        if (args[0]=="cat" and args[1].endswith("/post.json")
                and stale["remaining"]>0):
            stale["remaining"]-=1
            return b"wrong temporary cloud response"
        return original(args,data=data,timeout=timeout,allow_missing=allow_missing)
    cloud.runner=temporary_old_post
    status=inspect(cloud)
    assert status["sample_valid"]==1
    assert status["sample_mismatch"]==0
    assert stale["remaining"]==0
