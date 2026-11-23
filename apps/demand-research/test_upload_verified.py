"""Offline append-only regression tests; no real private archive or network calls."""
import hashlib
import json
from pathlib import Path

import pytest
import upload_verified as archive

REMOTE = "archive:DemandResearch"


def stage_post(root, pid, text="demo", media=b"sample media"):
    folder = root / "posts" / pid
    folder.mkdir(parents=True, exist_ok=True)
    key = "posts/" + pid + "/media/0001.jpg"
    (folder / "media").mkdir()
    (folder / "media" / "0001.jpg").write_bytes(media)
    (folder / "post.json").write_text(json.dumps({"id": pid, "text": text,
        "media": [{"key": key, "mime": "image/jpeg", "bytes": len(media),
                    "sha256": hashlib.sha256(media).hexdigest()}]}), encoding="utf-8")


@pytest.fixture
def fake_remote(monkeypatch):
    store = {}
    writes = []

    def list_remote(prefix, directories=False):
        prefix = prefix.split(":", 1)[1].strip("/")
        prefix = prefix.removeprefix("DemandResearch").strip("/")
        prefix = prefix + "/" if prefix else ""
        names = set()
        for key in store:
            if not key.startswith(prefix):
                continue
            remainder = key[len(prefix):]
            if "/" in remainder:
                if directories:
                    names.add(remainder.split("/", 1)[0] + "/")
            elif not directories:
                names.add(remainder)
        return names

    def read_remote(remote, key):
        return store[key]

    def upload_file(path, remote, key, immutable=True):
        data = Path(path).read_bytes()
        if immutable and key in store and store[key] != data:
            raise RuntimeError("immutable conflict")
        store[key] = data
        writes.append(key)

    def upload_bytes(data, remote, key, immutable=True):
        if immutable and key in store and store[key] != data:
            raise RuntimeError("immutable conflict")
        store[key] = data
        writes.append(key)

    def remote_digest(remote, key, max_size):
        data = store[key]
        return len(data), hashlib.sha256(data).hexdigest()

    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE", "synthetic-credential")
    monkeypatch.setattr(archive, "list_remote", list_remote)
    monkeypatch.setattr(archive, "read_remote", read_remote)
    monkeypatch.setattr(archive, "upload_file", upload_file)
    monkeypatch.setattr(archive, "upload_bytes", upload_bytes)
    monkeypatch.setattr(archive, "remote_digest", remote_digest)
    return store, writes


def test_sequential_uploads_preserve_prior_records_and_history(tmp_path, fake_remote):
    store, writes = fake_remote
    a = "a" * 16
    b = "b" * 16
    first = tmp_path / "first"
    second = tmp_path / "second"
    stage_post(first, a, "first")
    stage_post(second, b, "second")
    assert archive.publish(first, REMOTE)["added"] == 1
    original_catalog = store["metadata/catalog.json"]
    original_media = store[f"posts/{a}/media/0001.jpg"]
    result = archive.publish(second, REMOTE)
    assert result["posts"] == 2
    assert result["added"] == 1
    assert store[f"posts/{a}/media/0001.jpg"] == original_media
    catalog = json.loads(store["metadata/catalog.json"])
    assert [p["id"] for p in catalog["posts"]] == [a, b]
    old_sha = hashlib.sha256(original_catalog).hexdigest()
    assert store[f"metadata/catalog-history/{old_sha}.json"] == original_catalog
    assert writes.count(f"posts/{a}/media/0001.jpg") == 1


def test_retry_is_idempotent_without_remote_writes(tmp_path, fake_remote):
    store, writes = fake_remote
    pid = "a" * 16
    stage_post(tmp_path, pid)
    archive.publish(tmp_path, REMOTE)
    before = len(writes)
    result = archive.publish(tmp_path, REMOTE)
    assert result["added"] == 0
    assert result["unchanged"] == 1
    assert len(writes) == before


def test_conflicting_duplicate_aborts_before_remote_writes(tmp_path, fake_remote):
    store, writes = fake_remote
    pid = "a" * 16
    first = tmp_path / "first"
    second = tmp_path / "second"
    stage_post(first, pid, "original")
    stage_post(second, pid, "mutated")
    archive.publish(first, REMOTE)
    before = dict(store)
    before_writes = len(writes)
    with pytest.raises(RuntimeError, match="append-only"):
        archive.publish(second, REMOTE)
    assert store == before
    assert len(writes) == before_writes


def test_invalid_catalog_aborts_without_overwriting(tmp_path, fake_remote):
    store, writes = fake_remote
    store["metadata/catalog.json"] = b"{broken"
    stage_post(tmp_path, "a" * 16)
    with pytest.raises(RuntimeError, match="invalid"):
        archive.publish(tmp_path, REMOTE)
    assert writes == []
    assert store["metadata/catalog.json"] == b"{broken"


def test_orphan_posts_abort_without_catalog(tmp_path, fake_remote):
    store, writes = fake_remote
    store["posts/deadbeefdeadbeef/post.json"] = b"orphan"
    stage_post(tmp_path, "a" * 16)
    with pytest.raises(RuntimeError, match="unrelated orphan"):
        archive.publish(tmp_path, REMOTE)
    assert writes == []


def test_remote_readback_failure_does_not_publish_catalog(tmp_path, fake_remote, monkeypatch):
    store, writes = fake_remote
    stage_post(tmp_path, "a" * 16)
    monkeypatch.setattr(archive, "remote_digest", lambda remote, key, max_size: (0, "wrong"))
    with pytest.raises(RuntimeError, match="integrity mismatch"):
        archive.publish(tmp_path, REMOTE)
    assert "metadata/catalog.json" not in store


def test_concurrent_catalog_change_stops_last_write(tmp_path, fake_remote, monkeypatch):
    store, writes = fake_remote
    first = tmp_path / "first"
    second = tmp_path / "second"
    stage_post(first, "a" * 16)
    archive.publish(first, REMOTE)
    stage_post(second, "b" * 16)
    normal_load = archive.load_catalog
    calls = 0

    def simulate_change(remote, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            old = json.loads(store["metadata/catalog.json"])
            old["other_writer"] = True
            store["metadata/catalog.json"] = json.dumps(old).encode()
        return normal_load(remote, **kwargs)

    monkeypatch.setattr(archive, "load_catalog", simulate_change)
    before_catalog = store["metadata/catalog.json"]
    with pytest.raises(RuntimeError, match="Concurrent"):
        archive.publish(second, REMOTE)
    assert store["metadata/catalog.json"] != before_catalog
    assert json.loads(store["metadata/catalog.json"])["other_writer"] is True


def test_resume_after_interrupted_initial_upload(tmp_path, fake_remote, monkeypatch):
    store, writes = fake_remote
    pid = "a" * 16
    stage_post(tmp_path, pid)
    normal_digest = archive.remote_digest
    monkeypatch.setattr(archive, "remote_digest", lambda *args: (0, "wrong"))
    with pytest.raises(RuntimeError, match="integrity mismatch"):
        archive.publish(tmp_path, REMOTE)
    assert "metadata/catalog.json" not in store
    monkeypatch.setattr(archive, "remote_digest", normal_digest)
    assert archive.publish(tmp_path, REMOTE)["added"] == 1
    assert len(json.loads(store["metadata/catalog.json"])["posts"]) == 1


def test_missing_credentials_aborts_without_remote_access(tmp_path, fake_remote, monkeypatch):
    store, writes = fake_remote
    stage_post(tmp_path, "a" * 16)
    monkeypatch.delenv("RCLONE_CONFIG_ARCHIVE_COOKIE")
    with pytest.raises(RuntimeError, match="secret is missing"):
        archive.publish(tmp_path, REMOTE)
    assert store == {} and writes == []
