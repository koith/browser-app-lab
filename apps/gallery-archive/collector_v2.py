#!/usr/bin/env python3
"""Collector V2: independent bounded acquisition, durable queue and real-byte staging.

Input is the existing curated public-work-pages registry; never guess paid media
URLs or reuse the old direct_photo_pipeline. Existing publisher performs the
final same-frame deduplication and immutable Pages transaction.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from html import unescape
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from PIL import Image
import requests

ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = "GalleryCollectorV2/0.1 (public pages only; respectful crawling)"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
PRIORITY = {
    "mimmi": ("djawa-pop-kitty-party", "djawa-nikke-yuni",
              "djawa-janus-scary-lantern-night", "djawa-rudy2-codename-wolfgirl",
              "djawa-twin-bunnies-affair"),
    "yui": ("yui-meow-public-samples", "artgravia-677-yui-public-samples",
            "djawa-privaty-public-samples", "artgravia-639-yui-public-samples"),
}
RETRY_SECONDS = {
    "new_staged": 86400, "unchanged": 604800, "no_public_images": 604800,
    "blocked": 2592000, "unverified_page": 604800, "fetch_error": 172800,
}
SCHEMA = 1


class DownloadFailure(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def public_https(value):
    if not isinstance(value, str) or len(value) > 2000:
        return False
    try:
        u = urlsplit(value.strip())
        host = (u.hostname or "").lower().rstrip(".")
        if (u.scheme != "https" or not host or u.username or u.password
                or u.port not in (None, 443) or "." not in host
                or host in ("localhost", "metadata.google.internal")
                or host.endswith((".local", ".localhost", ".internal", ".test"))
                or any(c.isspace() for c in value)):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return True
    except ValueError:
        return False


def usable_image_url(url):
    return public_https(url) and urlsplit(url).path.lower().endswith(IMAGE_EXTS)


def load_inventory(root, model):
    if model not in PRIORITY:
        raise ValueError("unknown model")
    base = Path(root) / "apps" / (model + "-gallery")
    src = json.loads((base / "public-work-pages.json").read_text(encoding="utf-8"))
    owner = json.loads((base / "owner-index.json").read_text(encoding="utf-8"))
    stored = json.loads((base / "stored-albums.json").read_text(encoding="utf-8"))
    known = set()
    counts = defaultdict(set)
    for book in owner.get("albums", []) + stored.get("albums", []):
        for item in book.get("images", []):
            sha = item.get("sha256")
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha):
                known.add(sha)
                counts[book["id"]].add(sha)
    works = []
    for a in src.get("albums", []):
        aid = a.get("id")
        urls = list(dict.fromkeys(u for u in [a.get("source"), *(a.get("source_pages") or [])]
                                  if public_https(u)))
        if not isinstance(aid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}", aid):
            continue
        if not urls:
            continue
        expected = next((a[k] for k in ("advertised_photos", "public_web_edition_photos",
                                       "source_claimed_total_edition_photos")
                         if type(a.get(k)) is int and 1 <= a[k] <= 25000), None)
        works.append({"id": aid, "title": a.get("title") or aid, "urls": urls,
                      "priority": (PRIORITY[model].index(aid)
                                   if aid in PRIORITY[model] else 100 + int(a.get("priority") or 0)),
                      "observed_sha_count": len(counts[aid]), "expected": expected,
                      "gap": max(0, expected - len(counts[aid])) if expected else None})
    works.sort(key=lambda a: (a["priority"], -(a["gap"] or 0), a["id"]))
    return works, known


class QueueDB:
    """SQLite executes the queue; a compact JSON checkpoint survives runner loss."""
    def __init__(self, path, snapshot=None, now=None):
        self.now = time.time() if now is None else float(now)
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS work (id TEXT PRIMARY KEY, "
                        "checked REAL NOT NULL, next_at REAL NOT NULL, attempts INTEGER NOT NULL, "
                        "status TEXT NOT NULL, staged INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS media (url TEXT PRIMARY KEY, "
                        "sha TEXT NOT NULL, checked REAL NOT NULL)")
        if snapshot and Path(snapshot).is_file():
            doc = json.loads(Path(snapshot).read_text(encoding="utf-8"))
            if doc.get("schema_version") != SCHEMA:
                raise ValueError("invalid checkpoint version")
            for r in doc.get("works", []):
                if len(r) == 6:
                    self.db.execute("INSERT OR REPLACE INTO work VALUES (?,?,?,?,?,?)", r)
            for r in doc.get("media", []):
                if len(r) == 3 and public_https(r[0]):
                    self.db.execute("INSERT OR REPLACE INTO media VALUES (?,?,?)", r)
        self.db.commit()

    def eligible(self, works, max_works):
        ready = []
        for w in works:
            row = self.db.execute("SELECT next_at FROM work WHERE id=?", (w["id"],)).fetchone()
            if row is None or row[0] <= self.now:
                ready.append(w)
        return ready[:max_works]

    def visited_media(self, url):
        row = self.db.execute("SELECT checked FROM media WHERE url=?", (url,)).fetchone()
        return bool(row and row[0] > self.now - 1209600)

    def remember_media(self, url, sha):
        self.db.execute("INSERT OR REPLACE INTO media VALUES (?,?,?)",
                        (url, sha, self.now))
        self.db.commit()

    def finish(self, aid, status, staged):
        if status not in RETRY_SECONDS:
            raise ValueError("unknown queue status")
        old = self.db.execute("SELECT attempts FROM work WHERE id=?", (aid,)).fetchone()
        self.db.execute("INSERT OR REPLACE INTO work VALUES (?,?,?,?,?,?)",
                        (aid, self.now, self.now + RETRY_SECONDS[status],
                         (old[0] if old else 0) + 1, status, int(staged)))
        self.db.commit()

    def checkpoint(self, path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": SCHEMA,
                "works": self.db.execute("SELECT id,checked,next_at,attempts,status,staged "
                                         "FROM work ORDER BY id").fetchall(),
                "media": self.db.execute("SELECT url,sha,checked FROM media ORDER BY url").fetchall()}
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
                       encoding="utf-8")
        os.replace(tmp, target)


class PublicHTTP:
    """No credentials, guessed media URLs, private hosts, robots bypass or hidden APIs."""
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.robots = {}

    def permitted(self, url):
        if not public_https(url):
            return False
        u = urlsplit(url)
        origin = u.scheme + "://" + u.netloc
        if origin not in self.robots:
            robots_url = origin + "/robots.txt"
            try:
                res = self.session.get(robots_url, timeout=(6, 10),
                                       allow_redirects=False)
                if res.status_code == 404:
                    self.robots[origin] = None
                elif res.status_code == 200 and len(res.content) <= 500000:
                    parser = RobotFileParser()
                    parser.parse(res.text.splitlines())
                    self.robots[origin] = parser
                else:
                    self.robots[origin] = False
            except requests.RequestException:
                self.robots[origin] = False
        rule = self.robots[origin]
        return rule is None or (rule is not False and rule.can_fetch(USER_AGENT, url))

    def fetch(self, url, *, kind, max_bytes):
        current = url
        for _ in range(4):
            if not self.permitted(current):
                raise DownloadFailure("blocked_robots_or_nonpublic_url")
            try:
                response = self.session.get(current, timeout=(8, 22), stream=True,
                                            allow_redirects=False)
                if response.status_code in (301, 302, 303, 307, 308):
                    target = urljoin(current, response.headers.get("Location", ""))
                    response.close()
                    if not public_https(target):
                        raise DownloadFailure("blocked_redirect_target")
                    current = target
                    continue
                if response.status_code in (401, 403, 429):
                    raise DownloadFailure("blocked_http_" + str(response.status_code))
                if response.status_code != 200:
                    raise DownloadFailure("http_" + str(response.status_code))
                content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
                if kind == "html" and content_type and "html" not in content_type:
                    raise DownloadFailure("not_html")
                if kind == "image" and content_type and not (
                        content_type.startswith("image/") or
                        content_type == "application/octet-stream"):
                    raise DownloadFailure("not_image")
                raw = bytearray()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > max_bytes:
                        raise DownloadFailure("size_limit")
                return bytes(raw)
            except requests.RequestException as exc:
                raise DownloadFailure("network_" + type(exc).__name__) from exc
            finally:
                if "response" in locals():
                    response.close()
        raise DownloadFailure("redirect_limit")


def is_specific_edition(work, page):
    """Do not file photos from generic timelines or author/catalogue indexes."""
    path = urlsplit(page).path.lower().rstrip("/")
    if path.endswith(("/media", "/portfolio-cat/mimmi", "/yui", "/mimmi")):
        return False
    title = work["title"].lower()
    return bool(title and work["id"])


def page_candidates(raw, origin, max_candidates=160):
    soup = BeautifulSoup(raw, "html.parser")
    for node in soup.select("script,style,nav,footer,aside,header,.related,.sidebar"):
        node.decompose()
    container = soup.select_one("article .entry-content, article .post-content, "
                                "article, main .entry-content, main, #powerbbsContent")
    if container is None:
        return []
    result = []
    seen = set()

    def add(url):
        if not isinstance(url, str):
            return
        url = urljoin(origin, unescape(url.strip()))
        if usable_image_url(url) and url not in seen:
            seen.add(url)
            result.append(url)

    for tag in container.select("img, source"):
        parent = tag.parent
        if parent and parent.name == "a":
            add(parent.get("href"))
        srcset = tag.get("srcset") or tag.get("data-srcset") or ""
        for part in reversed(srcset.split(",")):
            add(part.strip().split(" ")[0])
        for attr in ("data-full", "data-original", "data-src", "src"):
            add(tag.get(attr))
    for tag in container.select("a[href]"):
        if tag.find("img") is None:
            add(tag.get("href"))
    return result[:max_candidates]


def inspect_photo(raw):
    if len(raw) < 4500 or len(raw) > 40000000:
        raise DownloadFailure("invalid_image_bytes")
    try:
        with Image.open(BytesIO(raw)) as img:
            fmt = img.format
            img.verify()
        with Image.open(BytesIO(raw)) as img:
            img.load()
            w, h = img.size
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DownloadFailure("invalid_decoded_photo") from exc
    if fmt not in ("JPEG", "PNG", "WEBP") or min(w, h) < 300 or w * h > 100000000:
        raise DownloadFailure("invalid_photo_dimensions")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "width": w, "height": h,
            "ext": {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]}


def collect(root, model, stage, state_file, *, max_works=5, max_photos=20,
            max_pages_per_work=3, deadline_seconds=600, http=None, now=None):
    if not (1 <= max_works <= 200 and 1 <= max_photos <= 500
            and 1 <= max_pages_per_work <= 20 and 1 <= deadline_seconds <= 3600):
        raise ValueError("invalid bounded campaign")
    stage = Path(stage)
    stage.mkdir(parents=True, exist_ok=True)
    works, known = load_inventory(root, model)
    queue = QueueDB(stage / "queue.sqlite", state_file, now=now)
    selected = queue.eligible(works, max_works)
    client = http or PublicHTTP()
    cutoff = time.monotonic() + deadline_seconds
    report = {"model": model, "registered_works": len(works),
              "eligible_works": len(selected), "works": [],
              "new_physical_sha_staged": 0, "bytes_staged": 0,
              "gallery_verified": False}
    albums = []
    session_sha = set()
    for work in selected:
        if time.monotonic() >= cutoff or len(session_sha) >= max_photos:
            break
        details = {"id": work["id"], "pages": 0, "media_candidates": 0,
                   "files_staged": 0, "known_sha": 0, "errors": {}}
        photos = []
        pages_without_failure = 0
        for page in work["urls"][:max_pages_per_work]:
            if time.monotonic() >= cutoff or len(session_sha) >= max_photos:
                break
            if not is_specific_edition(work, page):
                details["errors"]["generic_page_needs_adapter"] = (
                    details["errors"].get("generic_page_needs_adapter", 0) + 1)
                continue
            try:
                page_raw = client.fetch(page, kind="html", max_bytes=3000000)
                details["pages"] += 1
                candidates = page_candidates(page_raw, page)
                details["media_candidates"] += len(candidates)
                pages_without_failure += 1
            except DownloadFailure as exc:
                details["errors"][exc.code] = details["errors"].get(exc.code, 0) + 1
                continue
            for url in candidates:
                if len(session_sha) >= max_photos or time.monotonic() >= cutoff:
                    break
                if queue.visited_media(url):
                    continue
                try:
                    raw = client.fetch(url, kind="image", max_bytes=40000000)
                    meta = inspect_photo(raw)
                except DownloadFailure as exc:
                    details["errors"][exc.code] = details["errors"].get(exc.code, 0) + 1
                    continue
                queue.remember_media(url, meta["sha256"])
                if meta["sha256"] in known or meta["sha256"] in session_sha:
                    details["known_sha"] += 1
                    continue
                # The renderer/publisher independently detects visual re-encodes
                # and upgrades. A distinct SHA here is NOT a new gallery photo.
                rel = ("originals/" + work["id"] + "/" +
                       meta["sha256"][:20] + "." + meta["ext"])
                dest = stage / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.read_bytes() != raw:
                    raise ValueError("immutable stage collision")
                if not dest.exists():
                    temp = dest.with_suffix(".partial")
                    temp.write_bytes(raw)
                    os.replace(temp, dest)
                session_sha.add(meta["sha256"])
                photos.append({"key": rel, "sha256": meta["sha256"],
                               "bytes": meta["bytes"], "width": meta["width"],
                               "height": meta["height"], "number": len(photos) + 1,
                               "source_url": url,
                               "numbering_provenance": "archive_append_order_not_publisher_number"})
                report["bytes_staged"] += meta["bytes"]
                details["files_staged"] += 1
        if photos:
            albums.append({"id": work["id"], "title": work["title"], "images": photos})
        if details["files_staged"]:
            status = "new_staged"
        elif pages_without_failure:
            status = "unchanged" if details["media_candidates"] else "no_public_images"
        elif any(k.startswith("blocked") for k in details["errors"]):
            status = "blocked"
        elif "generic_page_needs_adapter" in details["errors"] and len(details["errors"]) == 1:
            status = "unverified_page"
        else:
            status = "fetch_error"
        queue.finish(work["id"], status, details["files_staged"])
        details["status"] = status
        report["works"].append(details)
    report["new_physical_sha_staged"] = len(session_sha)
    metadata = stage / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "catalog.json").write_text(
        json.dumps({"model": model, "albums": albums}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (metadata / "collector-v2-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    queue.checkpoint(state_file)
    queue.db.close()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["mimmi", "yui"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--max-works", type=int, default=5)
    parser.add_argument("--max-photos", type=int, default=20)
    parser.add_argument("--max-pages-per-work", type=int, default=3)
    parser.add_argument("--deadline-seconds", type=int, default=600)
    parser.add_argument("--plan-only", action="store_true")
    a = parser.parse_args()
    works, known = load_inventory(a.root, a.model)
    state = a.state or a.root / "apps/gallery-archive/verification" / (
        "collector-v2-" + a.model + ".json")
    if a.plan_only:
        q = QueueDB(":memory:", state)
        selected = q.eligible(works, a.max_works)
        print("COLLECTOR_V2_PLAN", json.dumps({
            "model": a.model, "known_sha": len(known),
            "eligible": [dict(id=w["id"], saved=w["observed_sha_count"], gap=w["gap"])
                         for w in selected]}, ensure_ascii=False))
        return
    result = collect(a.root, a.model, a.stage, state, max_works=a.max_works,
                     max_photos=a.max_photos, max_pages_per_work=a.max_pages_per_work,
                     deadline_seconds=a.deadline_seconds)
    print("COLLECTOR_V2_STAGED_NOT_YET_PUBLISHED", json.dumps(
        result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
