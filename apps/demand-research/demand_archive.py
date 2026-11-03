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
        self.catalog_unverified_refs = 0
        self._ensured_parents = set()

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
            elif re.search(r"409|already exists|duplicate|conflict", message):
                category = "duplicate"
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

    def read(self, key, *, cap=MAX_CATALOG, optional=False, domain=None):
        if not isinstance(key, str) or not key or ".." in key or "\\" in key:
            raise ValueError("unsafe remote key")
        args=["cat",self.remote+"/"+key,"--retries","2"]
        if domain:
            if domain!="https://nephobox.com":
                raise ValueError("unapproved alternate cloud endpoint")
            args.extend(["--terabox-domain",domain])
        data=self.command(args,timeout=120,allow_missing=optional)
        if data is None:
            return None
        if len(data) > cap:
            raise ValueError("private remote object exceeds cap")
        return data

    def read_verified(self, key, expected_digest, *, cap=MAX_POST):
        """Read SHA-matched object across bounded TeraBox stale-response windows.

        The cloud backend sometimes answers with older/empty bytes immediately
        after a successful upload. A single read mismatch is not corruption.
        This never overwrites or modifies the remote object.
        """
        if not re.fullmatch(r"[a-f0-9]{64}", str(expected_digest)):
            raise ValueError("unsafe expected checksum")
        # A single backend can serve stale bytes while the other endpoint
        # already serves the intended immutable object. Read from both domains
        # before labeling a verified journal/catalog object as corrupt.
        for domain, delays in (
            (None,(0.0,0.4,0.9,1.8,3.0)),
            ("https://nephobox.com",(0.0,0.5,1.0)),
        ):
            for delay in delays:
                if delay:
                    time.sleep(delay)
                try:
                    raw=self.read(key,cap=cap,optional=True,domain=domain)
                except (RuntimeError,ValueError):
                    raw=None
                if raw is not None and sha256(raw)==expected_digest:
                    return raw
        return None

    def names(self, prefix):
        raw = self.command(["lsf", self.remote + "/" + prefix,
                            "--files-only", "--retries", "2"], timeout=120, allow_missing=True)
        if raw is None:
            return []
        lines = raw.decode("utf-8", "replace").splitlines()
        if len(lines) > MAX_ENTRIES:
            raise ValueError("private archive entry listing too large")
        return lines

    def ensure_parent(self, key, *, domain=None, force=False):
        """Create and verify ancestors even when TeraBox directory views lag.

        The unofficial backend can acknowledge mkdir before apiFileUpload can
        resolve the new parent. The final directory must be observable before
        the first upload; a cached parent is rechecked on missing-path errors.
        No remote files are removed, renamed, or overwritten.
        """
        if domain not in (None, "https://nephobox.com"):
            raise ValueError("unapproved alternate cloud endpoint")
        parents=key.split("/")[:-1]
        final="/".join(parents)
        for idx in range(1,len(parents)+1):
            rel="/".join(parents[:idx])
            if rel in self._ensured_parents and not force and domain is None:
                continue
            dst=self.remote+"/"+rel
            opts=["--terabox-domain",domain] if domain else []
            last=None
            for delay in (0.0,0.6,1.5,3.0):
                if delay:
                    time.sleep(delay)
                try:
                    self.command(["mkdir",dst,*opts,"--retries","2"],timeout=90)
                except RuntimeError as error:
                    last=error
                    if "(authorization)" in str(error) or "(capacity)" in str(error):
                        raise
                    # A directory may already exist even if mkdir returned
                    # "duplicate" or a transient backend error. Only accept
                    # that case when an independent listing confirms it.
                    try:
                        visible=self.command(
                            ["lsf",dst,"--max-depth","1",*opts,"--retries","2"],
                            timeout=90,allow_missing=True)
                    except RuntimeError:
                        visible=None
                    if visible is None:
                        continue
                # Verify the deepest parent actually appears to this endpoint.
                # A successful mkdir alone is not a durable readiness proof.
                if rel==final:
                    try:
                        listed=self.command(
                            ["lsf",dst,"--max-depth","1",*opts,"--retries","2"],
                            timeout=90,allow_missing=True)
                    except RuntimeError as error:
                        last=error
                        listed=None
                    if listed is None:
                        continue
                self._ensured_parents.add(rel)
                break
            else:
                raise RuntimeError("private cloud parent directory unverified") from last

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
        # A missing response from one TeraBox host is not evidence that an
        # immutable original is absent on the other. Verify before writing.
        if existing is None:
            try:
                alternate_existing = self.read(
                    key,cap=cap,optional=True,domain="https://nephobox.com")
            except RuntimeError:
                alternate_existing = None
            if alternate_existing is not None:
                if sha256(alternate_existing)==expected_sha:
                    return False
                raise RuntimeError("immutable archive key collision: alternate endpoint checksum conflict")
        if existing is not None:
            if sha256(existing) == expected_sha:
                return False
            # No overwrite while an immutable object with other bytes is
            # visible. It might be a stale version of this same upload.
            if read_consistent()[0]:
                return False
            # Do not mutate an apparently existing immutable object. The
            # alternate endpoint may merely have caught up with a successful
            # earlier upload; a matching SHA is sufficient to accept it.
            for delay in (0.0,0.6,1.2):
                if delay:
                    time.sleep(delay)
                try:
                    alternate_existing=self.read(
                        key,cap=cap,optional=True,domain="https://nephobox.com")
                except (RuntimeError,ValueError):
                    alternate_existing=None
                if alternate_existing is not None and sha256(alternate_existing)==expected_sha:
                    return False
            raise RuntimeError("immutable archive key collision after dual-endpoint readback")

        # Bootstrap parents ahead of upload (not only after rclone fails).
        # This also covers a brand-new versioned catalog directory.
        try:
            self.ensure_parent(key)
        except RuntimeError as error:
            if any(code in str(error) for code in (
                    "(authorization)","(capacity)","(rate_limited)")):
                raise
            self.ensure_parent(key,domain="https://nephobox.com",force=True)
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
                        # A different runner or a provider inconsistency can
                        # invalidate a cached parent; reconstruct all levels.
                        self._ensured_parents.clear()
                        try:
                            self.ensure_parent(key,force=True)
                        except RuntimeError as parent_error:
                            if any(code in str(parent_error) for code in (
                                    "(authorization)","(capacity)","(rate_limited)")):
                                raise
                            # The primary host can be unable to recreate a
                            # newly-visible path even after the first upload.
                            # Give the alternate host a chance before failing.
                            try:
                                self.ensure_parent(
                                    key,domain="https://nephobox.com",force=True)
                            except RuntimeError:
                                pass
                matched, conflicting = read_consistent()
                if matched:
                    return True
                if conflicting:
                    # A different primary response is not proof of wrong media.
                    # Another endpoint can independently corroborate the exact
                    # original SHA. Never overwrite conflicting immutable bytes.
                    for delay in (0.0,0.5,1.0):
                        if delay:
                            time.sleep(delay)
                        try:
                            observed=self.read(key,cap=cap,optional=True,
                                               domain="https://nephobox.com")
                        except (RuntimeError,ValueError):
                            observed=None
                        if observed is not None and sha256(observed)==expected_sha:
                            return True
                    raise RuntimeError("private cloud readback did not converge")
            # The backend documents the same TeraBox account via nephobox.com
            # in regions where the primary upload host is intermittently broken.
            # Live synthetic copy/readback on 2026-11-03 succeeded. Try it only
            # after primary writes all fail; do not use for auth/quota/rate limits.
            if failure and any(code in str(failure) for code in
                               ("(authorization)","(capacity)","(rate_limited)")):
                raise RuntimeError("private cloud write blocked by account limits") from failure
            alternate="https://nephobox.com"
            before=None
            for delay in (0.0,0.6,1.2):
                if delay:
                    time.sleep(delay)
                try:
                    before=self.read(key,cap=cap,optional=True,domain=alternate)
                except RuntimeError:
                    before=None
                if before is not None:
                    if sha256(before)==expected_sha:
                        return True
                    raise RuntimeError("immutable alternate cloud endpoint checksum conflict")
            try:
                # A fresh nested directory can exist on one backend while
                # remaining temporarily unresolvable on the other.
                self.ensure_parent(key,domain=alternate,force=True)
                # Ignore any existing object even if TeraBox's listing API
                # is stale. Never intentionally overwrite an immutable key.
                self.command(["copyto",path,target,"--ignore-existing",
                              "--terabox-domain",alternate,"--retries","2"],timeout=130)
            except RuntimeError as error:
                failure=error
            for delay in (0.0,0.5,1.0,2.0,4.0):
                if delay:
                    time.sleep(delay)
                try:
                    observed=self.read(key,cap=cap,optional=True,domain=alternate)
                except RuntimeError:
                    observed=None
                if observed is not None:
                    if sha256(observed)==expected_sha:
                        return True
                    raise RuntimeError("immutable alternate cloud endpoint checksum conflict")
            raise RuntimeError("private cloud write unverified after primary and alternate endpoints") from failure
        finally:
            os.unlink(path)

    def load_catalog(self, *, include_entries=True):
        # The entry journal, not a large monolithic catalog, is the durable
        # source of truth. Catalogs are validated acceleration snapshots only.
        self.catalog_unverified_refs = 0
        legacy_raw = self.read("metadata/catalog.json",cap=MAX_CATALOG,optional=True)
        legacy = validate_catalog(json.loads(legacy_raw)) if legacy_raw is not None else []
        by_id={p["id"]:p for p in legacy}
        selected=None
        names=[n for n in self.names("metadata/manifests") if MANIFEST.fullmatch(n)]
        for name in sorted(names,key=lambda n:int(MANIFEST.fullmatch(n).group(1)),reverse=True):
            try:
                raw=self.read("metadata/manifests/"+name,cap=2048,optional=True)
                info=json.loads(raw) if raw is not None else None
                if (not isinstance(info,dict) or info.get("schema_version")!=1
                        or not re.fullmatch(r"metadata/catalogs/catalog-[0-9]{6,30}\.json",
                                            str(info.get("catalog","")))
                        or not re.fullmatch(r"[a-f0-9]{64}",str(info.get("sha256","")))):
                    continue
                blob=self.read_verified(info["catalog"],info["sha256"],cap=MAX_CATALOG)
                if blob is None:
                    continue
                parsed=json.loads(blob)
                if not isinstance(parsed,dict):
                    continue
                if parsed.get("schema_version")==1:
                    for p in validate_catalog(parsed):
                        by_id[p["id"]]=p
                    selected="legacy_inline"
                elif parsed.get("schema_version")==2:
                    refs=parsed.get("post_refs")
                    if not isinstance(refs,list) or len(refs)>MAX_POST:
                        continue
                    unique=set()
                    valid=True
                    for row in refs:
                        pid=row.get("id") if isinstance(row,dict) else None
                        digest=row.get("sha256") if isinstance(row,dict) else None
                        if (not isinstance(pid,str) or not ID.fullmatch(pid)
                                or not re.fullmatch(r"[a-f0-9]{64}",str(digest))
                                or pid in unique):
                            valid=False
                            break
                        unique.add(pid)
                    if not valid:
                        continue
                    selected=refs
                else:
                    continue
                break
            except (RuntimeError,ValueError,TypeError,KeyError,json.JSONDecodeError):
                continue
        if isinstance(selected,list):
            # Read-only SHA-verified materialization. A damaged reference cannot
            # erase an older verified record or stop unrelated entries loading.
            for row in selected:
                pid=row["id"]
                try:
                    raw=self.read_verified("posts/"+pid+"/post.json",
                                          row["sha256"],cap=MAX_POST)
                    if raw is None:
                        self.catalog_unverified_refs+=1
                        continue
                    item=validate_post(json.loads(raw))
                    if item["id"]!=pid:
                        raise ValueError("referenced post id mismatch")
                    by_id[pid]=item
                except (RuntimeError,ValueError,TypeError,KeyError,json.JSONDecodeError):
                    self.catalog_unverified_refs+=1
        if include_entries:
            # Read-only reconstruction works even if no catalog has EVER
            # published. This is the primary crash-recovery guarantee.
            by_id,_=self.recover_entries(by_id,repair=False)
        return sorted(by_id.values(),
                      key=lambda p:str(p.get("posted_at","")),reverse=True)

    def marker_ids(self):
        """List ID names without re-downloading every old post on every short poll.

        These are presence hints only, NOT verified archive totals. The separate
        integrity/recovery job continues byte-by-byte SHA256 validation.
        """
        ids=set()
        for directory in ("metadata/entries", "metadata/entries-repaired"):
            for name in self.names(directory):
                m=ENTRY.fullmatch(name)
                if m:
                    ids.add(m.group(1))
        return ids

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

    def corroborate_mismatched_post(self, pid, record):
        """Recover only if two independent immutable captures agree on identity,
        text, original timestamp and *every stored media checksum*.

        This never modifies post.json, capture.json, or the original marker;
        a separately named repaired marker preserves the conflicting evidence.
        """
        if not ID.fullmatch(str(pid)):
            return None
        try:
            post=validate_post(json.loads(record))
            if post["id"]!=pid:
                return None
            raw=self.read("posts/"+pid+"/capture.json",cap=100_000,optional=True)
            if raw is None:
                return None
            first=json.loads(raw)
            if not isinstance(first,dict) or first.get("id")!=pid:
                return None
            for field,other in (("platform","platform"),("source_url","source_url"),
                                ("posted_at","posted_at"),("text","text")):
                if first.get(field)!=post.get(other):
                    return None
            observed=first.get("observed_at")
            if not isinstance(observed,int):
                return None
            from datetime import datetime,timezone
            if post.get("captured_at")!=datetime.fromtimestamp(
                    observed,timezone.utc).isoformat():
                return None
            for media in post["media"]:
                blob=self.read(media["key"],cap=MAX_MEDIA_BYTES+1,optional=True)
                if blob is None or len(blob)!=media["bytes"] or sha256(blob)!=media["sha256"]:
                    return None
            # Check post bytes one more time to avoid signing a transient stale
            # read. The new marker remains immutable and SHA256-readback verified.
            if self.read("posts/"+pid+"/post.json",cap=MAX_POST)!=record:
                return None
            marker=canonical_json({"id":pid,"sha256":sha256(record)})
            self.write_immutable("metadata/entries-repaired/"+pid+".json",marker)
            if (self.read("metadata/entries-repaired/"+pid+".json",cap=1024)!=marker
                    or self.read("posts/"+pid+"/post.json",cap=MAX_POST)!=record):
                return None
            return post
        except (RuntimeError,ValueError,TypeError,KeyError,
                OverflowError,json.JSONDecodeError):
            return None

    def recover_entries(self, existing, *, repair=True):
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
                            # Read-only SHA verification against both approved
                            # endpoints can distinguish a stale primary read
                            # from truly different immutable content.
                            verified=self.read_verified(
                                "posts/"+pid+"/post.json",marker["sha256"],cap=MAX_POST)
                            if verified is not None:
                                record=verified
                            else:
                                proven=(self.corroborate_mismatched_post(pid,record)
                                        if repair and directory=="metadata/entries"
                                        else None)
                                if proven is not None:
                                    result[pid]=proven
                                    new+=1
                                    self.repaired_entries+=1
                                    continue
                                self.unrecoverable_entries += 1
                                self.quarantined_ids.add(pid)
                                continue
                    post = validate_post(json.loads(record))
                    if post["id"] != pid:
                        raise ValueError("marker/post mismatch")
                except (ValueError, TypeError, KeyError, json.JSONDecodeError, RuntimeError):
                    if directory != "metadata/entries" or not repair:
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

    def stage_partial_media(self, post, media_blobs=()):
        """Keep independently verified original attachment bytes across retries.

        No incomplete post.json or completed journal marker is published.
        Immutable per-slot checksum records are stored only in private cloud.
        """
        validate_post(post)
        pid=post["id"]
        blobs=list(media_blobs)
        if len(blobs)!=len(post["media"]):
            raise ValueError("missing staged media bytes")
        for media,blob in zip(post["media"],blobs):
            if (not isinstance(blob,bytes) or len(blob)!=media["bytes"]
                    or sha256(blob)!=media["sha256"]):
                raise ValueError("bad staged original media bytes")
            match=re.fullmatch(r"posts/"+pid+r"/media/([0-9]{4})\.[a-z0-9]+",media["key"])
            if match is None:
                raise ValueError("bad staged media source position")
            self.write_immutable(media["key"],blob)
            slot=match.group(1)
            marker={"id":pid,"index":int(slot),"key":media["key"],
                    "mime":media["mime"],"bytes":media["bytes"],
                    "sha256":media["sha256"]}
            self.write_immutable("metadata/media-parts/"+pid+"/"+slot+".json",
                                 canonical_json(marker))

    def read_staged_media(self,pid,index):
        """Return only a SHA-matched attachment from the original post/slot."""
        if not ID.fullmatch(str(pid)) or not isinstance(index,int) or not 1<=index<=16:
            raise ValueError("invalid staged media index")
        slot=str(index).zfill(4)
        raw=self.read("metadata/media-parts/"+pid+"/"+slot+".json",
                      cap=2048,optional=True)
        if raw is None:
            return None
        try:
            info=json.loads(raw)
            if (not isinstance(info,dict) or info.get("id")!=pid
                    or info.get("index")!=index or info.get("mime") not in MIMES
                    or not isinstance(info.get("bytes"),int)
                    or not 0<info["bytes"]<=MAX_MEDIA_BYTES
                    or not re.fullmatch(r"[a-f0-9]{64}",str(info.get("sha256","")))
                    or info.get("key")!="posts/"+pid+"/media/"+slot+MIMES[info["mime"]]):
                return None
            data=self.read_verified(info["key"],info["sha256"],
                                    cap=MAX_MEDIA_BYTES+1)
            if data is None or len(data)!=info["bytes"]:
                return None
            return info["mime"],data
        except (RuntimeError,ValueError,TypeError,KeyError,json.JSONDecodeError):
            return None

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
        if len(posts_by_id)>MAX_POST:
            raise ValueError("too many entries")
        # Compact v2 snapshot contains NO post text, accounts, profile URLs or
        # attachment links. Immutable post.json + entry journals own the bytes.
        refs=[]
        for pid,post in sorted(posts_by_id.items()):
            if not ID.fullmatch(str(pid)):
                continue
            try:
                validate_post(post)
            except ValueError:
                # Legacy inlined records remain available from catalog.json.
                continue
            refs.append({"id":pid,"sha256":sha256(canonical_json(post))})
        blob=canonical_json({"schema_version":2,"post_refs":refs})
        if len(blob)>MAX_CATALOG:
            raise ValueError("reference catalog too large")
        print("PRIVATE_CATALOG_PUBLISH_ATTEMPT",json.dumps({
            "records":len(refs),"bytes":len(blob),
            "index_format":"sha256_references_only",
            "versioned":True},sort_keys=True),flush=True)
        catalog="metadata/catalogs/catalog-"+str(run_id)+".json"
        manifest="metadata/manifests/manifest-"+str(run_id)+".json"
        self.write_immutable(catalog,blob)
        # Publish the pointer only AFTER the compact index is read back.
        self.write_immutable(manifest,canonical_json({
            "schema_version":1,"catalog":catalog,
            "sha256":sha256(blob),"posts":len(refs),
            "published_at":int(time.time())}))
        return {"posts":len(refs),"catalog_sha256_verified":True,
                "versioned":True,"index_format":"sha256_references_only"}

