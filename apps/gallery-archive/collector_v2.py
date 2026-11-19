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
from photo_visual_dedupe import WorkVisualIndex
from perceptual_duplicate_audit import scan_image, candidate_relation
from photo_quality_evidence import preferred_pair
from collector_v2_strategy import (publisher_targets, source_evidence_pages,
                                   verify_identity, best_observed_variants)

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
    official = publisher_targets(root, model)
    works = []
    for a in src.get("albums", []):
        aid = a.get("id")
        urls = list(dict.fromkeys(u for u in [a.get("source"), *(a.get("source_pages") or [])]
                                  if public_https(u)))
        if not isinstance(aid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}", aid):
            continue
        if not urls:
            continue
        publisher_count = official.get(aid, {}).get("declared_photo_count")
        source_count = next((a[k] for k in ("advertised_photos", "public_web_edition_photos",
                                            "source_claimed_total_edition_photos")
                             if type(a.get(k)) is int and 1 <= a[k] <= 25000), None)
        # Publisher-confirmed count beats preview-list labels and catalogue
        # claims. Union-of-SHA may still contain re-encodes, so the computed
        # gap is only a CONSERVATIVE minimum, never edition completion proof.
        expected = publisher_count or source_count
        works.append({"id": aid, "title": a.get("title") or aid, "urls": urls,
                      "priority": (PRIORITY[model].index(aid)
                                   if aid in PRIORITY[model] else 100 + int(a.get("priority") or 0)),
                      "observed_sha_count": len(counts[aid]), "expected": expected,
                      "target_basis": "publisher" if publisher_count else (
                          "public_source_claim" if source_count else "unknown"),
                      "declared_resolution": [
                          official.get(aid, {}).get("declared_width"),
                          official.get(aid, {}).get("declared_height")] if publisher_count else None,
                      "gap": max(0, expected - len(counts[aid])) if expected else None,
                      "missing_lower_bound_by_sha": max(0, expected - len(counts[aid]))
                          if expected else None})
    # Missing published cuts first, then unknown totals, finally albums whose
    # recorded SHA count already reaches their source-claimed public count.
    works.sort(key=lambda a: (
        0 if a["gap"] is not None and a["gap"] > 0 else
        1 if a["gap"] is None else 2,
        a["priority"], -(a["gap"] or 0), a["id"]))
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

    def visited_media(self, url, saved_sha=None):
        row = self.db.execute("SELECT sha,checked FROM media WHERE url=?", (url,)).fetchone()
        # A downloaded candidate isn't a published image. Retrying its URL
        # is necessary until the NEW SHA actually appears in the saved index.
        return bool(row and (saved_sha is None or row[0] in saved_sha)
                    and row[1] > self.now - 1209600)

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
        filename = urlsplit(url).path.rsplit("/", 1)[-1].lower()
        # Promotional graphics are not frames of the publisher's edition.
        # Keep the source bytes discoverable; exclude them from photo counts.
        if re.search(r"(?:^|[_-])(bn|banner|flyer|logo|cover|poster|pixibb)(?:[_.-]|$)", filename):
            return
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
    return best_observed_variants(result, max_candidates)


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
    # Reject third-party 512px cards and 600x800 site posters, not real
    # publisher-quality source photos. Never count small cards as new cuts.
    if fmt not in ("JPEG", "PNG", "WEBP") or min(w, h) < 900 or w * h > 100000000:
        raise DownloadFailure("invalid_photo_dimensions")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "width": w, "height": h,
            "ext": {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]}


def collect(root, model, stage, state_file, *, max_works=12, max_photos=48,
            max_per_work=6, max_pages_per_work=5, deadline_seconds=900,
            discovery_evidence=None, http=None, now=None):
    if not (1 <= max_works <= 200 and 1 <= max_photos <= 500
            and 1 <= max_per_work <= 500
            and 1 <= max_pages_per_work <= 20 and 1 <= deadline_seconds <= 3600):
        raise ValueError("invalid bounded campaign")
    stage = Path(stage)
    stage.mkdir(parents=True, exist_ok=True)
    works, known = load_inventory(root, model)
    evidence = {}
    if discovery_evidence:
        evidence_path = Path(discovery_evidence)
        if evidence_path.is_file():
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    extra_sources = source_evidence_pages(evidence, model, safe_url=public_https)
    extra_found = 0
    for work in works:
        added = [url for url in extra_sources.get(work["id"], [])
                 if url not in work["urls"]]
        work["discovered_urls"] = added
        work["urls"].extend(added)
        extra_found += len(added)
    base = Path(root) / "apps" / (model + "-gallery")
    saved = json.loads((base / "stored-albums.json").read_text(encoding="utf-8"))
    by_id = {a["id"]: a for a in saved.get("albums", [])}
    visual_indexes = {}
    queue = QueueDB(stage / "queue.sqlite", state_file, now=now)
    selected = queue.eligible(works, max_works)
    client = http or PublicHTTP()
    cutoff = time.monotonic() + deadline_seconds
    report = {"model": model, "registered_works": len(works),
              "eligible_works": len(selected),
              "admitted_discovered_pages": extra_found, "works": [],
              "new_physical_sha_staged": 0, "bytes_staged": 0,
              "gallery_verified": False, "counts_are_not_completion_proof": True}
    albums = []
    session_sha = set()
    for work in selected:
        if time.monotonic() >= cutoff or len(session_sha) >= max_photos:
            break
        details = {"id": work["id"], "pages": 0, "media_candidates": 0,
                   "files_staged": 0, "known_sha": 0, "same_frame_filtered": 0,
                   "errors": {}, "target_count": work["expected"],
                   "minimum_missing_by_sha": work["missing_lower_bound_by_sha"],
                   "target_basis": work["target_basis"],
                   "discovered_sources": len(work["discovered_urls"])}
        photos = []
        stage_visual = []
        if work["id"] not in visual_indexes:
            visual_indexes[work["id"]] = WorkVisualIndex(
                base, by_id.get(work["id"], {"id": work["id"], "images": []}))
        previous_visual = visual_indexes[work["id"]]
        pages_without_failure = 0
        for page in work["urls"][:max_pages_per_work]:
            if (time.monotonic() >= cutoff or len(session_sha) >= max_photos
                    or len(photos) >= min(max_per_work, max_photos)):
                break
            if not is_specific_edition(work, page):
                details["errors"]["generic_page_needs_adapter"] = (
                    details["errors"].get("generic_page_needs_adapter", 0) + 1)
                continue
            try:
                page_raw = client.fetch(page, kind="html", max_bytes=3000000)
                details["pages"] += 1
                matched, proof = verify_identity(
                    page_raw, work, model, discovered=page in work["discovered_urls"])
                if not matched:
                    details["errors"]["identity_"+proof] = (
                        details["errors"].get("identity_"+proof, 0) + 1)
                    continue
                candidates = page_candidates(page_raw, page)
                details["media_candidates"] += len(candidates)
                pages_without_failure += 1
            except DownloadFailure as exc:
                details["errors"][exc.code] = details["errors"].get(exc.code, 0) + 1
                continue
            for url in candidates:
                if (len(session_sha) >= max_photos or time.monotonic() >= cutoff
                        or len(photos) >= min(max_per_work, max_photos)):
                    break
                if queue.visited_media(url, known):
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
                # Drop proven same-frame recompressions BEFORE consuming the
                # finite staging budget. The independent publisher repeats
                # the same gate as defense-in-depth.
                existing_match = previous_visual.classify(raw)
                if existing_match and not existing_match["needs_replacement_transaction"]:
                    details["same_frame_filtered"] += 1
                    continue
                try:
                    scanned = scan_image(raw)
                    same_staged = next((
                        (old_raw, old_meta) for old_raw, old_meta in stage_visual
                        if (lambda relation, distance, diff:
                            relation == "perceptually_similar_review" and
                            distance is not None and distance <= 3 and
                            diff is not None and diff <= 2.0
                        )(*candidate_relation(old_meta, scanned))), None)
                except (OSError, ValueError):
                    scanned, same_staged = None, None
                if same_staged:
                    old_raw, old_meta = same_staged
                    higher, evidence = preferred_pair(
                        old_raw, raw, old_meta["sha256"])
                    if not (higher and evidence.get("same_photo_verified")):
                        details["same_frame_filtered"] += 1
                        continue
                # A distinct SHA here is STILL not a new gallery photo:
                # publisher independently validates real visual novelty.
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
                if scanned is not None:
                    stage_visual.append((raw, scanned))
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
        elif any(k.startswith("identity_") for k in details["errors"]):
            status = "unverified_page"
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
    parser.add_argument("--max-works", type=int, default=12)
    parser.add_argument("--max-photos", type=int, default=48)
    parser.add_argument("--max-per-work", type=int, default=6)
    parser.add_argument("--max-pages-per-work", type=int, default=5)
    parser.add_argument("--deadline-seconds", type=int, default=900)
    parser.add_argument("--discovery-evidence", type=Path)
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
            "eligible": [dict(id=w["id"], saved_SHA_upper_bound=w["observed_sha_count"],
                              minimum_missing=w["missing_lower_bound_by_sha"],
                              target=w["expected"], basis=w["target_basis"])
                         for w in selected]}, ensure_ascii=False))
        return
    result = collect(a.root, a.model, a.stage, state, max_works=a.max_works,
                     max_photos=a.max_photos, max_per_work=a.max_per_work,
                     max_pages_per_work=a.max_pages_per_work,
                     deadline_seconds=a.deadline_seconds,
                     discovery_evidence=a.discovery_evidence)
    print("COLLECTOR_V2_STAGED_NOT_YET_PUBLISHED", json.dumps(
        result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
