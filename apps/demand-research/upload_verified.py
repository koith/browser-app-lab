"""Add permissioned post bundles to a private TeraBox catalog without replacing old records.

Input: posts/<hex-id>/post.json and its media bytes. Only use sources with preservation
rights; no stage file or private credential belongs in the public repository.
The catalog is published last, and the previous version is preserved by SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

VALID_ID = re.compile(r"^[a-f0-9]{16,64}$")
VALID_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,150}$")
VALID_MIME = {"image/jpeg", "image/png", "image/webp", "image/avif", "video/mp4", "video/webm", "video/quicktime"}
MAX_MEDIA = 1500000000
MAX_CATALOG = 32 * 1024 * 1024


def digest(path):
    sha = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while b := f.read(1024 * 1024):
            sha.update(b)
            n += len(b)
    return n, sha.hexdigest()


def remote_digest(remote, key, max_size):
    target = remote.rstrip("/") + "/" + key
    p = subprocess.Popen(["rclone", "cat", target, "--timeout=65s", "--retries=2"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    sha = hashlib.sha256()
    n = 0
    try:
        while b := p.stdout.read(256 * 1024):
            n += len(b)
            if n > max_size:
                p.kill()
                p.wait()
                raise ValueError("Remote file exceeds declared size: " + key)
            sha.update(b)
        if p.wait(timeout=120):
            raise RuntimeError("Remote read failed: " + key)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    return n, sha.hexdigest()


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=180)


def list_remote(remote, directories=False):
    args = ["rclone", "lsf", remote, "--max-depth", "1"]
    args.append("--dirs-only" if directories else "--files-only")
    p = subprocess.run(args, capture_output=True, timeout=90)
    if p.returncode:
        raise RuntimeError("Unable to list remote; refusing to assume catalog is empty")
    return set(p.stdout.decode("utf-8").splitlines())


def read_remote(remote, key):
    p = subprocess.run(["rclone", "cat", remote.rstrip("/") + "/" + key],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120)
    if p.returncode or len(p.stdout) > MAX_CATALOG:
        raise RuntimeError("Remote catalog read failed or is too large")
    return p.stdout


def load_catalog(remote, pending_ids=None):
    def check_orphans():
        if pending_ids is None:
            raise RuntimeError("Remote has posts without a catalog; recovery needs the matching staged IDs")
        known = {pid + "/" for pid in pending_ids}
        actual = list_remote(remote.rstrip("/") + "/posts", directories=True)
        if not actual or not actual.issubset(known):
            raise RuntimeError("Remote has unrelated orphan posts; refusing to replace missing catalog")
    root = list_remote(remote, directories=True)
    if "metadata/" not in root:
        if "posts/" in root:
            check_orphans()
        return None, {"schema_version": 1, "posts": []}
    metadata = list_remote(remote.rstrip("/") + "/metadata")
    if "catalog.json" not in metadata:
        if "posts/" in root:
            check_orphans()
        return None, {"schema_version": 1, "posts": []}
    blob = read_remote(remote, "metadata/catalog.json")
    try:
        catalog = json.loads(blob)
        if not isinstance(catalog, dict) or catalog.get("schema_version") != 1:
            raise ValueError("Unknown catalog schema")
        posts = catalog.get("posts")
        if not isinstance(posts, list):
            raise ValueError("Invalid catalog records")
        ids = [p.get("id") for p in posts if isinstance(p, dict)]
        if len(ids) != len(posts) or any(not isinstance(x, str) or not VALID_ID.fullmatch(x) for x in ids):
            raise ValueError("Invalid catalog post id")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate catalog ids")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Existing catalog is invalid; refusing to overwrite") from exc
    return blob, catalog


def upload_file(path, remote, key, immutable=True):
    args = ["rclone", "copyto", str(path), remote.rstrip("/") + "/" + key]
    if immutable:
        args.append("--immutable")
    else:
        args.append("--ignore-times")
    run(*args)


def upload_bytes(data, remote, key, immutable=True):
    with tempfile.TemporaryDirectory(prefix="intersection-catalog-") as tmp:
        path = Path(tmp) / "payload.json"
        path.write_bytes(data)
        upload_file(path, remote, key, immutable=immutable)


def verified_remote(remote, key, data):
    n, sha = remote_digest(remote, key, len(data) + 1)
    if n != len(data) or sha != hashlib.sha256(data).hexdigest():
        raise RuntimeError("Remote readback mismatch: " + key)


def prepare(stage):
    stage = Path(stage).resolve()
    if not stage.is_dir() or not (stage / "posts").is_dir():
        raise ValueError("Missing local post-bundle folder")
    posts = []
    for folder in sorted((stage / "posts").iterdir()):
        if not folder.is_dir():
            continue
        pid = folder.name
        if not VALID_ID.fullmatch(pid):
            raise ValueError("Unsafe post directory name")
        manifest = folder / "post.json"
        if not manifest.is_file():
            raise ValueError("Missing post manifest: " + pid)
        post = json.loads(manifest.read_text(encoding="utf-8"))
        if post.get("id") != pid or not isinstance(post.get("text"), str) or not isinstance(post.get("media"), list):
            raise ValueError("Invalid post schema: " + pid)
        for m in post["media"]:
            if not isinstance(m, dict):
                raise ValueError("Invalid media record: " + pid)
            key = m.get("key", "")
            prefix = "posts/" + pid + "/media/"
            if (not isinstance(key, str) or not key.startswith(prefix)
                    or not VALID_NAME.fullmatch(key[len(prefix):])
                    or m.get("mime") not in VALID_MIME):
                raise ValueError("Invalid media path/type: " + pid)
            path = stage / key
            if not path.is_file():
                raise ValueError("Missing media file: " + key)
            size, sha = digest(path)
            if not 0 < size <= MAX_MEDIA or size != m.get("bytes") or sha != m.get("sha256"):
                raise ValueError("Local integrity failure: " + key)
            m["remote_verified"] = True  # Only published after actual readback.
        posts.append(post)
    if not posts:
        raise ValueError("No post bundles found; nothing uploaded")
    return stage, posts


def publish(stage, remote):
    if not os.getenv("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("TeraBox secret is missing; upload was not attempted")
    if not remote.startswith("archive:") or "/" in remote.split(":", 1)[0]:
        raise ValueError("Invalid TeraBox remote")
    stage, staged_posts = prepare(stage)
    old_blob, catalog = load_catalog(remote, pending_ids={p["id"] for p in staged_posts})  # Before writes.
    by_id = {p["id"]: p for p in catalog["posts"]}
    new_posts = []
    unchanged = 0
    for post in staged_posts:
        existing = by_id.get(post["id"])
        if existing is not None:
            if existing != post:
                raise RuntimeError("Existing post differs; append-only archive refuses update: " + post["id"])
            unchanged += 1
        else:
            new_posts.append(post)
    if not new_posts:
        return {"posts": len(catalog["posts"]), "added": 0, "unchanged": unchanged,
                "verified_files": 0, "catalog_sha256": hashlib.sha256(old_blob).hexdigest() if old_blob else None,
                "remote": remote}

    verified = 0
    for post in new_posts:
        for m in post["media"]:
            upload_file(stage / m["key"], remote, m["key"], immutable=True)
            n, sha = remote_digest(remote, m["key"], m["bytes"] + 1)
            if n != m["bytes"] or sha != m["sha256"]:
                raise RuntimeError("Remote integrity mismatch: " + m["key"])
            verified += 1
        blob = (json.dumps(post, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        key = "posts/" + post["id"] + "/post.json"
        upload_bytes(blob, remote, key, immutable=True)
        verified_remote(remote, key, blob)
        verified += 1

    if old_blob is not None:
        old_sha = hashlib.sha256(old_blob).hexdigest()
        history_key = "metadata/catalog-history/" + old_sha + ".json"
        upload_bytes(old_blob, remote, history_key, immutable=True)
        verified_remote(remote, history_key, old_blob)

    latest_blob, _ = load_catalog(remote, pending_ids={p["id"] for p in new_posts} if old_blob is None else None)
    if latest_blob != old_blob:
        raise RuntimeError("Concurrent catalog update detected; refusing to overwrite")
    updated = dict(catalog)
    updated["posts"] = catalog["posts"] + new_posts
    content = (json.dumps(updated, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if len(content) > MAX_CATALOG:
        raise RuntimeError("Catalog exceeds size limit; old catalog remains intact")
    upload_bytes(content, remote, "metadata/catalog.json", immutable=False)
    verified_remote(remote, "metadata/catalog.json", content)
    return {"posts": len(updated["posts"]), "added": len(new_posts),
            "unchanged": unchanged, "verified_files": verified,
            "catalog_sha256": hashlib.sha256(content).hexdigest(), "remote": remote}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--remote", default="archive:DemandResearch")
    args = parser.parse_args()
    print(json.dumps(publish(args.stage, args.remote), ensure_ascii=False))
