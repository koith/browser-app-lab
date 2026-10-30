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
    """Rotate among distinct smallest albums before trying another frame."""
    albums = []
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
                rel, digest = photo.get("url", ""), photo.get("sha256", "")
                if (not isinstance(rel, str) or not rel.startswith("stored-albums/")
                    or any(bit in ("", ".", "..") for bit in rel.split("/"))
                    or not SHA.fullmatch(digest)
                    or not re.search(r"\.(?:jpe?g|png|webp)$", rel, re.I)):
                    continue
                valid.append((rel, digest))
            if not valid:
                continue
            positions = list(dict.fromkeys((0, len(valid) // 2, len(valid) - 1)))
            photos = []
            for position in positions:
                rel, digest = valid[position]
                photos.append({
                    "model": model, "album_id": album["id"],
                    "album_title": album.get("title", ""),
                    "album_saved_public_count": len(valid),
                    "photo_sha256": digest,
                    "public_image_url": f"{PAGES}/{model}-gallery/{quote(rel, safe='/')}",
                })
            albums.append(photos)
    albums.sort(key=lambda photos: (
        photos[0]["album_saved_public_count"],
        photos[0]["model"], photos[0]["album_id"]))
    # Seek first distinct album, then the second and third frame.
    # This avoids exhausting a run on three photos from one 7-photo album.
    return [photo for index in range(3) for album in albums
            for photo in album[index:index + 1]]


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



def tineye_query(session: requests.Session, public_image_url: str, timeout=20) -> dict:
    """Public URL search used by SearXNG's TinEye engine; no paid API or login."""
    try:
        response = session.get("https://tineye.com/api/v1/result_json/",
                               params={"page": 1, "url": public_image_url},
                               timeout=(8, timeout), allow_redirects=False,
                               headers={"Accept": "application/json"})
        if response.status_code != 200:
            return {"status": f"http_{response.status_code}", "links": []}
        if "json" not in response.headers.get("Content-Type", "").lower():
            return {"status": "not_json", "links": []}
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
            return {"status": "invalid_results", "links": []}
        links, seen = [], set()
        for match in payload["matches"][:100]:
            if not isinstance(match, dict):
                continue
            score = match.get("score", 0)
            # High visual similarity; discovery only, not an album identity.
            if not isinstance(score, (int, float)) or score < 75:
                continue
            for back in match.get("backlinks", [])[:10]:
                if not isinstance(back, dict):
                    continue
                target = untrack(back.get("backlink", ""))
                if target and target not in seen:
                    links.append({"url": target, "label": "TinEye visual match",
                                  "visual_match_score": score,
                                  "matched_width": match.get("width"),
                                  "matched_height": match.get("height")})
                    seen.add(target)
        return {"status": "leads_found" if links else "no_readable_public_matches",
                "links": links[:80]}
    except (requests.RequestException, ValueError, TypeError) as err:
        return {"status": "request_" + type(err).__name__, "links": []}


def yandex_query(session: requests.Session, public_image_url: str, timeout=20) -> dict:
    """Ordinary Yandex Images image-URL results; do not bypass bot challenges."""
    try:
        response = session.get("https://yandex.com/images/search",
                               params={"rpt": "imageview", "url": public_image_url},
                               timeout=(8, timeout), allow_redirects=False)
        if response.status_code != 200:
            return {"status": f"http_{response.status_code}", "links": []}
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            return {"status": "not_html", "links": []}
        if response.headers.get("x-yandex-captcha") == "captcha":
            return {"status": "captcha_not_bypassed", "links": []}
        if len(response.content) > 4_000_000:
            return {"status": "response_too_large", "links": []}
        links = leads_from_html(response.text)
        return {"status": "leads_found" if links else "no_readable_public_matches",
                "links": links[:80]}
    except requests.RequestException as err:
        return {"status": "network_" + type(err).__name__, "links": []}


def multi_search(session: requests.Session, public_image_url: str) -> dict:
    """Independent paths: an inaccessible Lens result does not stop image search."""
    merged, seen, statuses = [], set(), {}
    for name, method in (("lens", lens_query), ("tineye", tineye_query),
                         ("yandex", yandex_query)):
        outcome = method(session, public_image_url)
        statuses[name] = outcome["status"]
        for link in outcome.get("links", []):
            if link["url"] not in seen:
                merged.append({**link, "search_engine": name})
                seen.add(link["url"])
    return {"status": " | ".join(f"{k}={v}" for k, v in statuses.items()),
            "engine_statuses": statuses, "links": merged[:100]}


MODEL_MATCH = {
    "mimmi": re.compile(r"mimmi|mimmissu17|밈미|밈미", re.I),
    "yui": re.compile(r"sim\s*yui|yui\s*sim|심유이|심혜성|super_yuisan|沈惠星|沈慧圣|ゆい|유이", re.I),
}
YUI_SINGLE = re.compile(r"\\byui\\b", re.I)
STUDIO = re.compile(r"\\bsweet\\s?box\\b|\\bswtb\\b|artgravia|athletic club|"
                    r"wet yui|teddy bear|thru thru|yui.s present|cream soda", re.I)


def identity_supported(row: dict, link: dict) -> bool:
    """Check exact artist hints, never mistake an arbitrary visual neighbor for her."""
    url = link.get("url", "")
    label = link.get("label", "")
    if not isinstance(url, str) or not isinstance(label, str):
        return False
    target = unquote(urlsplit(url).path).replace("-", " ").replace("_", " ")
    combined = f"{label} {target}"
    model = row["model"]
    if MODEL_MATCH[model].search(combined):
        return True
    if model == "yui" and YUI_SINGLE.search(combined):
        # Generic Yui alone is insufficient; require her work/studio context.
        title = row.get("album_title", "")
        relevant = [x for x in re.findall(r"[a-z]{4,}", title.lower())
                    if x not in {"sweetbox", "photo", "public", "swtb", "yui"}]
        return bool(STUDIO.search(combined)
                    or any(token in combined.lower() for token in relevant))
    return False


def discover(root: Path = ROOT, max_seeds=10, offset=0, delay=2.0,
             engine=multi_search, session=None) -> dict:
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
        relevant = [link for link in links if identity_supported(seed, link)]
        rows.append({**seed, "engine": "google_lens_tineye_yandex_public",
                     "search_status": evidence.get("status"),
                     "engine_statuses": evidence.get("engine_statuses", {}),
                     "off_model_match_rejected": len(links) - len(relevant),
                     "candidate_pages": relevant,
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
        "engine_status_counts": {name: {status: sum(
            r["engine_statuses"].get(name, "not_run") == status for r in rows)
            for status in sorted(set(r["engine_statuses"].get(name, "not_run") for r in rows))}
            for name in ("lens", "tineye", "yandex")},
        "candidate_page_urls": len({p["url"] for x in rows for p in x["candidate_pages"]}),
        "off_model_match_rejected": sum(x["off_model_match_rejected"] for x in rows),
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
                               "candidate_page_urls", "off_model_match_rejected", "engine_status_counts", "new_private_photos_stored",
                               "gallery_images_added")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
