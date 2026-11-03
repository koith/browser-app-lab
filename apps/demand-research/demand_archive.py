"""Private append-only TeraBox capture store for source-verified, retention-permitted records.

No public repository content, account cookies, credentials or post bodies in logs.
Per-post entry markers are immutable and durable before the versioned catalog is published.
A crashed catalog publication is repaired by reconciling entry markers on the next run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

ID = re.compile(r"^[a-f0-9]{40}$")
MANIFEST = re.compile(r"^manifest-([0-9]{6,30})\.json$")
ENTRY = re.compile(r"^([a-f0-9]{40})\.json$")
MIMES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
         "image/avif": ".avif", "video/mp4": ".mp4",
         "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_CATALOG = 70_000_000
MAX_POST = 100_000
MAX_MEDIA_BYTES = 80_000_000
MAX_ENTRIES = 150_000
PLATFORMS = {"bluesky", "mastodon", "misskey", "lemmy", "reddit", "x", "threads", "instagram"}


def canonical_json(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def public_url(raw):
    if not isinstance(raw, str) or len(raw) > 2048:
        return False
    try:
        u = urlsplit(raw)
        return (u.scheme == "https" and bool(u.hostname)
                and not u.username and not u.password and not u.fragment
                and not u.hostname.lower().endswith((".local", ".internal"))
                and u.hostname.lower() not in ("localhost", "127.0.0.1"))
    except ValueError:
        return False


def post_key(platform, original_id):
    if platform not in PLATFORMS or not isinstance(original_id, str) or not 4 <= len(original_id) <= 1000:
        raise ValueError("invalid original post identifier")
    return hashlib.sha256((platform + "\x00" + original_id).encode("utf-8")).hexdigest()[:40]


def validate_post(p):
    if not isinstance(p, dict) or not ID.fullmatch(str(p.get("id", ""))):
        raise ValueError("bad post id")
    if p.get("platform") not in PLATFORMS or not isinstance(p.get("text"), str) or len(p["text"]) > 30000:
        raise ValueError("invalid post content")
    if not public_url(p.get("source_url")) or not isinstance(p.get("posted_at"), str):
        raise ValueError("invalid source evidence")
    media = p.get("media")
    if not isinstance(media, list) or len(media) > 16:
        raise ValueError("invalid media list")
    for m in media:
        if (not isinstance(m, dict) or m.get("mime") not in MIMES
                or not isinstance(m.get("bytes"), int)
                or not 0 < m["bytes"] <= MAX_MEDIA_BYTES
                or not re.fullmatch(r"[a-f0-9]{64}", str(m.get("sha256", "")))
                or m.get("remote_verified") is not True
                or not re.fullmatch(r"posts/" + p["id"] + r"/media/[0-9]{4}\.[a-z0-9]+", str(m.get("key", "")))):
            raise ValueError("unverified or unsafe media")
    return p


def validate_catalog(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("posts"), list):
        raise ValueError("invalid catalog")
    if len(payload["posts"]) > MAX_POST:
        raise ValueError("catalog too many posts")
    seen = set()
    for p in payload["posts"]:
        validate_post(p)
        if p["id"] in seen:
            raise ValueError("duplicate post")
        seen.add(p["id"])
    return payload["posts"]


class CloudArchive:
    def __init__(self, remote=None, runner=None):
        self.remote = (remote or os.getenv("DEMAND_TERABOX_REMOTE", "archive:DemandResearch")).rstrip("/")
        if not re.fullmatch(r"archive:[A-Za-z0-9_/-]+", self.remote):
            raise ValueError("archive destination must be a private archive: prefix")
        self.runner = runner or self._run

    @staticmethod
    def _run(args, data=None, timeout=150, allow_missing=False):
        try:
            r = subprocess.run(["rclone", *args], input=data, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RuntimeError("private cloud command could not execute") from e
        if r.returncode:
            if allow_missing:
                return None
            raise RuntimeError("private cloud request failed")
        return r.stdout

    def command(self, args, *, timeout=150, allow_missing=False):
        return self.runner(args, timeout=timeout, allow_missing=allow_missing)

    def preflight(self):
        if not os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"):
            raise RuntimeError("private TeraBox authentication not configured")
        self.command(["lsf", "archive:", "--max-depth", "1", "--retries", "2"], timeout=90)

    def read(self, key, *, cap=MAX_CATALOG, optional=False):
        if not isinstance(key, str) or not key or ".." in key or "\\" in key:
            raise ValueError("unsafe remote key")
        data = self.command(["cat", self.remote + "/" + key, "--retries", "2"],
                            timeout=120, allow_missing=optional)
        if data is None:
            return None
        if len(data) > cap:
            raise ValueError("private remote object exceeds cap")
        return data

    def names(self, prefix):
        raw = self.command(["lsf", self.remote + "/" + prefix,
                            "--files-only", "--retries", "2"], timeout=120, allow_missing=True)
        if raw is None:
            return []
        lines = raw.decode("utf-8", "replace").splitlines()
        if len(lines) > MAX_ENTRIES:
            raise ValueError("private archive entry listing too large")
        return lines

    def write_immutable(self, key, data):
        if not isinstance(data, bytes):
            raise TypeError("cloud content must be bytes")
        existing = self.read(key, cap=len(data) + 1, optional=True)
        if existing is not None:
            if sha256(existing) != sha256(data):
                raise RuntimeError("immutable archive key collision")
            return False
        with tempfile.NamedTemporaryFile(prefix="demand-cloud-", delete=False) as temp:
            temp.write(data)
            path = temp.name
        try:
            self.command(["copyto", path, self.remote + "/" + key, "--retries", "3"],
                         timeout=240)
            saved = self.read(key, cap=len(data) + 1)
            if saved != data:
                raise RuntimeError("cloud content SHA256 readback mismatch")
        finally:
            os.unlink(path)
        return True

    def load_catalog(self):
        names = [n for n in self.names("metadata/manifests") if MANIFEST.fullmatch(n)]
        # The newest fully verified catalog is the only authoritative pointer.
        for name in sorted(names, key=lambda n: int(MANIFEST.fullmatch(n).group(1)), reverse=True):
            raw = self.read("metadata/manifests/" + name, cap=2048, optional=True)
            if raw is None:
                continue
            try:
                info = json.loads(raw)
                if (info.get("schema_version") != 1 or not
                    re.fullmatch(r"metadata/catalogs/catalog-[0-9]{6,30}\.json", str(info.get("catalog", "")))
                    or not re.fullmatch(r"[a-f0-9]{64}", str(info.get("sha256", "")))):
                    continue
                cat = self.read(info["catalog"], cap=MAX_CATALOG)
                if sha256(cat) != info["sha256"]:
                    continue
                return validate_catalog(json.loads(cat))
            except (ValueError, KeyError, json.JSONDecodeError, RuntimeError):
                continue
        legacy = self.read("metadata/catalog.json", cap=MAX_CATALOG, optional=True)
        return validate_catalog(json.loads(legacy)) if legacy is not None else []

    def recover_entries(self, existing):
        result = dict(existing)
        new = 0
        for filename in self.names("metadata/entries"):
            match = ENTRY.fullmatch(filename)
            if not match or match.group(1) in result:
                continue
            key = "metadata/entries/" + filename
            entry = json.loads(self.read(key, cap=1024))
            pid = match.group(1)
            if entry.get("id") != pid or not re.fullmatch(r"[a-f0-9]{64}", str(entry.get("sha256", ""))):
                raise ValueError("invalid archive entry marker")
            raw = self.read("posts/" + pid + "/post.json", cap=MAX_POST)
            if sha256(raw) != entry["sha256"]:
                raise RuntimeError("private post record checksum mismatch")
            post = validate_post(json.loads(raw))
            if post["id"] != pid:
                raise ValueError("private post identifier mismatch")
            result[pid] = post
            new += 1
        return result, new

    def save_post(self, post, media_blobs=()):
        validate_post(post)
        pid = post["id"]
        blobs = list(media_blobs)
        if len(blobs) != len(post["media"]):
            raise ValueError("missing original media bytes")
        for item, blob in zip(post["media"], blobs):
            if not isinstance(blob, bytes) or len(blob) != item["bytes"] or sha256(blob) != item["sha256"]:
                raise ValueError("bad original media bytes")
            self.write_immutable(item["key"], blob)
        raw = canonical_json(post)
        self.write_immutable("posts/" + pid + "/post.json", raw)
        self.write_immutable("metadata/entries/" + pid + ".json",
                             canonical_json({"id": pid, "sha256": sha256(raw)}))
        return pid

    def publish_catalog(self, posts_by_id, run_id):
        if not re.fullmatch(r"[0-9]{6,30}", str(run_id)):
            raise ValueError("invalid publication ID")
        rows = [validate_post(v) for _, v in sorted(posts_by_id.items())]
        blob = canonical_json({"schema_version": 1, "posts": rows})
        if len(blob) > MAX_CATALOG:
            raise ValueError("catalog too large")
        catalog = "metadata/catalogs/catalog-" + str(run_id) + ".json"
        manifest = "metadata/manifests/manifest-" + str(run_id) + ".json"
        self.write_immutable(catalog, blob)
        # Last write: pointer always refers to a readable, verified catalog.
        self.write_immutable(manifest, canonical_json({
            "schema_version": 1, "catalog": catalog,
            "sha256": sha256(blob), "posts": len(rows), "published_at": int(time.time())}))
        return {"posts": len(rows), "catalog_sha256_verified": True, "versioned": True}
