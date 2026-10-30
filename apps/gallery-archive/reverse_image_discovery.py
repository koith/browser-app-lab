#!/usr/bin/env python3
"""Prioritize image-first discovery from PHYSICALLY STORED, publicly hosted photos.

Neither a reverse-search match nor a reachable URL is a stored image.
This worker does not fetch third-party photo bytes, publish files, access private
TeraBox media, or use captcha/proxy/login workarounds. It produces bounded
research leads for independently verified public-source collectors.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://koith.github.io/browser-app-lab/apps"
MODELS = ("mimmi", "yui")
KNOWN_SOURCES = {
    "djawaphoto.com", "www.djawaphoto.com", "www.cosmeitu.com",
    "cosmeitu.com", "www.4khd.com", "4khd.com", "www.4kgirl.com",
    "4kgirl.com", "www.coserbox.com", "coserbox.com",
    "cosplaytele.com", "www.cosplaytele.com", "www.xiantuji.com",
    "xiantuji.com", "www.huantuji.com", "huantuji.com",
    "www.chaotuji.com", "chaotuji.com", "www.simimiao.com",
    "simimiao.com", "www.miaojishe.com", "miaojishe.com",
    "www.vtacoser.com", "vtacoser.com", "www.ruanmeimiao.com",
    "ruanmeimiao.com", "www.v2ph.com", "v2ph.com",
    "www.yingyuge.com", "yingyuge.com", "www.coslm.com",
    "coslm.com", "www.mncos.com", "mncos.com",
    "www.coserpic.com", "coserpic.com", "www.sood42.com",
    "sood42.com", "www.cosp.jp", "cosp.jp",
}
SEARCH_DOMAINS = {"google.com", "www.google.com", "lens.google.com",
                  "www.bing.com", "bing.com", "tineye.com", "www.tineye.com"}
SHA = re.compile(r"^[a-f0-9]{64}$")


def physical_seeds(root: Path = ROOT) -> list[dict]:
    """Only use already PUBLIC GitHub Pages photos, never private owner catalog."""
    all_seeds = []
    for model in MODELS:
        path = root / f"{model}-gallery" / "stored-albums.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("model", model) != model or not isinstance(doc.get("albums"), list):
            raise ValueError(f"Invalid on-disk {model} photo manifest")
        for album in doc["albums"]:
            images = album.get("images", [])
            if not images or re.search(r"AI Enhanced|AI 보정", album.get("title", ""), re.I):
                continue
            valid = []
            for photo in images:
                file = photo.get("url", "")
                digest = photo.get("sha256", "")
                # No external links, "..", URL schemes or nonphysical photo rows.
                if (not isinstance(file, str) or not file.startswith("stored-albums/")
                    or any(bit in ("", ".", "..") for bit in file.split("/"))
                    or not SHA.fullmatch(digest)
                    or not re.search(r"\.(?:jpe?g|png|webp)$", file, re.I)):
                    continue
                valid.append((file, digest))
            if not valid:
                continue
            # Balanced edge/center choices, with few-photo albums first.
            positions = list(dict.fromkeys((0, len(valid) // 2, len(valid) - 1)))
            for position in positions:
                rel, digest = valid[position]
                url = f"{PAGES}/{model}-gallery/{quote(rel, safe='/')}"
                all_seeds.append({
                    "model": model, "album_id": album["id"],
                    "album_title": album.get("title", ""),
                    "album_saved_public_count": len(valid),
                    "photo_sha256": digest, "public_image_url": url,
                })
    return sorted(all_seeds, key=lambda row: (
        row["album_saved_public_count"], row["model"], row["album_id"],
        row["public_image_url"]))


def untrack(url: str) -> str | None:
    """Reject search UI, unsafe schemes, credentials and fake nested URLs."""
    for _ in range(2):
        try:
            p = urlsplit(url)
        except ValueError:
            return None
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            return None
        if p.hostname in SEARCH_DOMAINS and p.path in ("/url", "/search"):
            q = parse_qs(p.query)
            nested = (q.get("q") or q.get("url") or [""])[0]
            if nested.startswith("https://"):
                url = nested
                continue
        if p.hostname in KNOWN_SOURCES:
            return p._replace(fragment="").geturl()
        return None
    return None


class ResultLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        url = dict(attrs).get("href", "")
        if not url:
            return
        url = untrack(url)
        if url:
            self.current = {"url": url, "label": ""}

    def handle_data(self, data):
        if self.current:
            self.current["label"] = (self.current["label"] + " " + data).strip()[:200]

    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            self.links.append(self.current)
            self.current = None


def leads_from_html(html: str) -> list[dict]:
    parser = ResultLinks()
    parser.feed(html[:2_000_000])
    urls = set()
    output = []
    for link in parser.links:
        if link["url"] not in urls:
            urls.add(link["url"])
            output.append(link)
    return output


def lens_query(session: requests.Session, public_image_url: str, timeout=18) -> dict:
    """Standard public Google Lens URL flow; do NOT evade search limitations."""
    target = "https://lens.google.com/uploadbyurl"
    try:
        response = session.get(target, params={"url": public_image_url},
                               timeout=(8, timeout), allow_redirects=True,
                               headers={"User-Agent": "GalleryPersonalArchiveResearch/1.0"})
        if response.status_code != 200:
            return {"status": f"http_{response.status_code}", "links": []}
        host = urlsplit(response.url).hostname or ""
        if host not in ("www.google.com", "google.com", "lens.google.com"):
            return {"status": "unexpected_redirect", "links": []}
        if "text/html" not in response.headers.get("Content-Type", ""):
            return {"status": "not_html", "links": []}
        # Dynamic or challenged search is not a successful retrieval.
        links = leads_from_html(response.text)
        return {"status": "leads_found" if links else "no_readable_public_matches",
                "links": links[:80]}
    except requests.RequestException as error:
        return {"status": "network_" + type(error).__name__, "links": []}


def discover(root: Path = ROOT, max_seeds=10, offset=0, delay=2.0,
             engine=lens_query, session=None) -> dict:
    seeds = physical_seeds(root)
    if max_seeds < 1 or max_seeds > 30 or offset < 0:
        raise ValueError("Limit each image search to 1–30 public seed photos")
    selected = ([seeds[(offset + i) % len(seeds)]
                 for i in range(min(max_seeds, len(seeds)))]) if seeds else []
    session = session or requests.Session()
    rows = []
    for n, seed in enumerate(selected):
        evidence = engine(session, seed["public_image_url"])
        links = evidence.get("links", [])
        rows.append({**seed, "engine": "google_lens_public",
                     "search_status": evidence.get("status"),
                     "candidate_pages": links,
                     "new_private_photos_stored": 0,
                     "new_gallery_photos_visible": 0})
        if n + 1 < len(selected) and delay:
            time.sleep(delay)
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "reverse-image-search-using-existing-public-SHA-file",
        "total_public_seed_candidates": len(seeds),
        "seed_queries": len(rows),
        "search_readable_results": sum(bool(x["candidate_pages"]) for x in rows),
        "candidate_page_urls": len({p["url"] for x in rows for p in x["candidate_pages"]}),
        "new_private_photos_stored": 0, "gallery_images_added": 0,
        "research_only_not_acquired": True, "results": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    if not 0 <= args.delay <= 20:
        parser.error("Bound delay at 0–20 seconds")
    result = discover(max_seeds=args.seeds, offset=args.offset, delay=args.delay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print("GALLERY_REVERSE_IMAGE_RESEARCH", json.dumps({
        k: result[k] for k in ("seed_queries", "search_readable_results",
                               "candidate_page_urls", "new_private_photos_stored",
                               "gallery_images_added")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
