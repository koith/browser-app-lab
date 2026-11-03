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

    def fake(self, args, timeout=150, allow_missing=False):
        op = args[0]
        if op == "lsf":
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
    with pytest.raises(RuntimeError, match="checksum"):
        cloud.recover_entries({})


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
         "record": {"text": "섹트 상품 후기", "createdAt": "2026-11-03T00:00:00Z"},
         "embed": {"images": [{"fullsize": "https://cdn.bsky.app/img/something.jpg"}]}},
        {"uri": "at://did:plc:abcdefghijk/app.bsky.feed.post/restricted",
         "author": {"did": "did:plc:abcdefghijk"},
         "record": {"text": "섹트 private", "createdAt": "2026-11-03T00:00:00Z"},
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
