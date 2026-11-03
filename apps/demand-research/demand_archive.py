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
    # Keep legacy permissioned TeraBox catalogs intact. They may have older
    # 16/64-hex IDs and omit the new capture-only provenance/date fields.
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("posts"), list):
        raise ValueError("invalid catalog")
    if len(payload["posts"]) > MAX_POST:
        raise ValueError("catalog too many posts")
    seen = set()
    for p in payload["posts"]:
        if not isinstance(p, dict) or not re.fullmatch(r"[a-f0-9]{16,64}", str(p.get("id", ""))):
            raise ValueError("bad catalog post id")
        if p["id"] in seen:
            raise ValueError("duplicate catalog post")
        seen.add(p["id"])
        if not isinstance(p.get("text"), str) or len(p["text"]) > 30000:
            raise ValueError("invalid catalog body")
        media = p.get("media")
        if not isinstance(media, list) or len(media) > 100:
            raise ValueError("invalid catalog attachments")
        for m in media:
            if not isinstance(m, dict) or m.get("mime") not in MIMES:
                raise ValueError("invalid catalog media type")
            key = m.get("key", "")
            if (not isinstance(key, str) or not key.startswith("posts/" + p["id"] + "/media/")
                    or ".." in key or "\\" in key or "%" in key
                    or not isinstance(m.get("bytes"), int) or not 0 < m["bytes"] <= 1_500_000_000
                    or not re.fullmatch(r"[a-f0-9]{64}", str(m.get("sha256", "")))
                    or m.get("remote_verified") is not True):
                raise ValueError("unverified catalog media")
    return payload["posts"]

class CloudArchive:
    def __init__(self, remote=None, runner=None):
        self.remote = (remote or os.getenv("DEMAND_TERABOX_REMOTE", "archive:DemandResearch")).rstrip("/")
        if not re.fullmatch(r"archive:[A-Za-z0-9_/-]+", self.remote):
            raise ValueError("archive destination must be a private archive: prefix")
        self.runner = runner or self._run
        self.quarantined_ids = set()
        self.repaired_entries = 0
        self.unrecoverable_entries = 0

    @staticmethod
    def _run(args, data=None, timeout=150, allow_missing=False):
        try:
            r = subprocess.run(["rclone", *args], input=data, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RuntimeError("private cloud command could not execute") from e
        if r.returncode:
            # Diagnostics contain error classes only. Never print cookie, remote
            # paths, source text, URLs or raw backend error output to Actions.
            message = r.stderr.decode("utf-8", "replace").lower()
            if re.search(r"not found|does not exist|doesn't exist|no such file|directory not found", message):
                category = "missing"
            elif re.search(r"429|rate.limit|too many requests|throttl", message):
                category = "rate_limited"
            elif re.search(r"403|permission|access.denied|unauthorized|cookie", message):
                category = "authorization"
            elif re.search(r"quota|space|capacity", message):
                category = "capacity"
            elif re.search(r"timeout|timed out|deadline|connection", message):
                category = "network_timeout"
            elif re.search(r"500|502|503|504|server.error", message):
                category = "remote_server"
            else:
                category = "backend_rejected"
            if allow_missing and category == "missing":
                return None
            raise RuntimeError("private cloud " + args[0] + " failed (" + category + ")")
        return r.stdout

    def command(self, args, *, data=None, timeout=150, allow_missing=False):
        return self.runner(args, data=data, timeout=timeout, allow_missing=allow_missing)

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
        cap = max(len(data) + 1, MAX_MEDIA_BYTES + MAX_POST)
        expected_sha = sha256(data)

        def read_consistent():
            # TeraBox may briefly show stale remote bytes after successful
            # copyto/rcat. Never treat a single mismatching cat as authoritative.
            last = None
            for delay in (0.0, 0.4, 0.8, 1.5, 2.5, 4.0, 5.0):
                if delay:
                    time.sleep(delay)
                try:
                    last = self.read(key, cap=cap, optional=True)
                except RuntimeError:
                    last = None
                if last is not None and sha256(last) == expected_sha:
                    return True, False
            return False, last is not None

        existing = self.read(key, cap=cap, optional=True)
        if existing is not None:
            if sha256(existing) == expected_sha:
                return False
            # No overwrite while an immutable object with other bytes is
            # visible. It might be a stale version of this same upload.
            if read_consistent()[0]:
                return False
            raise RuntimeError("immutable archive key collision after readback retries")

        with tempfile.NamedTemporaryFile(prefix="demand-cloud-", delete=False) as temp:
            temp.write(data)
            path = temp.name
        try:
            target = self.remote + "/" + key
            failure = None
            for attempt in range(4):
                method = "rcat" if attempt % 2 and len(data) < 2_000_000 else "copyto"
                try:
                    if method == "copyto":
                        self.command(["copyto", path, target, "--retries", "2"], timeout=130)
                    else:
                        self.command(["rcat", target, "--retries", "2"],
                                     data=data, timeout=130)
                except RuntimeError as error:
                    failure = error
                    if "(missing)" in str(error):
                        # A missing parent directory is distinguishable from
                        # stale object visibility; idempotent mkdir is safe.
                        try:
                            self.command(["mkdir", self.remote + "/" + key.rsplit("/", 1)[0]],
                                         timeout=90)
                        except RuntimeError:
                            pass
                matched, conflicting = read_consistent()
                if matched:
                    return True
                if conflicting:
                    # Never repeatedly overwrite apparently different remote
                    # bytes: preserve both states for integrity investigation.
                    raise RuntimeError("private cloud readback did not converge")
            raise RuntimeError("private cloud write unverified after alternate methods") from failure
        finally:
            os.unlink(path)

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

    def pending_capture_ids(self, existing):
        # Early snapshots survive a crash even before a verified entry is written.
        raw = self.command(["lsf", self.remote + "/posts", "--dirs-only",
                            "--retries", "2"], timeout=120, allow_missing=True)
        if raw is None:
            return []
        names = raw.decode("utf-8", "replace").splitlines()
        if len(names) > MAX_ENTRIES:
            raise ValueError("private capture directory listing exceeds limit")
        return [name[:-1] for name in names if name.endswith("/")
                and ID.fullmatch(name[:-1]) and name[:-1] not in existing
                and name[:-1] not in self.quarantined_ids]

    def recover_entries(self, existing):
        result = dict(existing)
        new = 0
        self.repaired_entries = 0
        self.unrecoverable_entries = 0
        # Repaired markers are preferred. Damaged legacy markers are never
        # overwritten or deleted; only re-signed after independent readback.
        for directory in ("metadata/entries-repaired", "metadata/entries"):
            for filename in self.names(directory):
                match = ENTRY.fullmatch(filename)
                if not match or match.group(1) in result or match.group(1) in self.quarantined_ids:
                    continue
                pid = match.group(1)
                key = directory + "/" + filename
                try:
                    marker_raw = self.read(key, cap=1024)
                    marker = json.loads(marker_raw)
                    if (not isinstance(marker, dict) or marker.get("id") != pid
                            or not re.fullmatch(r"[a-f0-9]{64}",
                                                str(marker.get("sha256", "")))):
                        raise ValueError("bad entry metadata")
                    record = self.read("posts/" + pid + "/post.json", cap=MAX_POST)
                    if sha256(record) != marker["sha256"]:
                        # Never rebuild a valid signed marker from different
                        # bytes. A remote read can be briefly stale; retry
                        # before quarantining this record without erasing it.
                        for _ in range(2):
                            time.sleep(0.5)
                            record = self.read("posts/" + pid + "/post.json", cap=MAX_POST)
                            if sha256(record) == marker["sha256"]:
                                break
                        else:
                            self.unrecoverable_entries += 1
                            self.quarantined_ids.add(pid)
                            continue
                    post = validate_post(json.loads(record))
                    if post["id"] != pid:
                        raise ValueError("marker/post mismatch")
                except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                    if directory != "metadata/entries":
                        self.unrecoverable_entries += 1
                        continue
                    # Recovery is allowed only if a separately readable post
                    # validates and a new marker can be written/read back twice.
                    try:
                        record = self.read("posts/" + pid + "/post.json",
                                           cap=MAX_POST, optional=True)
                        if record is None:
                            self.unrecoverable_entries += 1
                            continue
                        post = validate_post(json.loads(record))
                        if post["id"] != pid:
                            self.unrecoverable_entries += 1
                            continue
                        marker_data = canonical_json({"id": pid, "sha256": sha256(record)})
                        self.write_immutable("metadata/entries-repaired/" + filename,
                                             marker_data)
                        if self.read("posts/" + pid + "/post.json", cap=MAX_POST) != record:
                            raise RuntimeError("repaired post changed during readback")
                        self.repaired_entries += 1
                    except (ValueError, TypeError, KeyError, json.JSONDecodeError,
                            RuntimeError):
                        self.unrecoverable_entries += 1
                        continue
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
        key = "posts/" + pid + "/post.json"
        try:
            self.write_immutable(key, raw)
        except RuntimeError:
            # An earlier attempt may already have succeeded, despite a transient
            # provider write error. Reuse only a fully valid same-source record.
            old_raw = self.read(key, cap=MAX_POST, optional=True)
            if old_raw is None:
                raise
            old = validate_post(json.loads(old_raw))
            if (old["id"] != pid or old["platform"] != post["platform"]
                    or old.get("source_url") != post.get("source_url")
                    or old.get("posted_at") != post.get("posted_at")):
                raise RuntimeError("different existing post at immutable key")
            raw = old_raw
            post = old
        marker=canonical_json({"id": pid, "sha256": sha256(raw)})
        try:
            self.write_immutable("metadata/entries/" + pid + ".json", marker)
        except (RuntimeError, ValueError):
            # A previously corrupted immutable marker must not hold up all
            # future captures; use a distinct verified repair namespace.
            self.write_immutable("metadata/entries-repaired/" + pid + ".json", marker)
        return post

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
