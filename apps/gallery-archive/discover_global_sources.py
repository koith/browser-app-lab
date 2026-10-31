#!/usr/bin/env python3
"""Read-only cross-region discovery of photo-work references for Yui and Mimmi.

A catalogue title is not a downloaded image. This module never touches gallery
manifests, photo bytes, cloud credentials or authentication-protected URLs.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
APPS = ROOT.parent
REGISTRY = ROOT / "global_source_registry.json"
OUTPUT = ROOT / "global-source-leads.json"
AGENT = "PhotoCatalogueAudit/1.0 (public HTML metadata only; no image downloads)"
NUMBERED = re.compile(r"\bNO\.\s*0*(\d{1,3})(?:\s+|\s*[\-–:.：]\s*)(.{3,190})", re.I)
PHOTOS = re.compile(r"[\[【〖(（]\s*(\d{1,4})\s*P(?=[^A-Za-z]|$)", re.I)
MODEL_WORDS = {
    "yui": ("심유이", "심혜성", "沈惠星", "沈慧圣", "super_yuisan", "Yui Sim", "ゆい", "Yui"),
    "mimmi": ("밈미", "밈미", "Mimmi", "Mimmissu17", "Mimmi_official"),
}
TITLE_NOISE = re.compile(
    r"\b(?:djawa|photo|cosplay|cream\s*soda|creamsoda|mimmi|mimmissu17|yui|swtb|"
    r"album|ai\s*enhanced|public|preview)\b|밈미|심유이|유이|ゆい|写真|공개|웹판",
    re.I,
)


def normalized(text: str) -> str:
    s = unicodedata.normalize("NFKC", text).casefold()
    s = re.sub(r"[\[【〖(（]\s*\d{1,4}\s*p(?:\b|[+／-]).{0,45}?[\]】〗)）]", "", s, flags=re.I)
    s = TITLE_NOISE.sub(" ", s)
    return " ".join(re.findall(r"[\w]+", s)).strip()


def relevant(text: str, model: str) -> bool:
    s = unicodedata.normalize("NFKC", text).casefold()
    for word in MODEL_WORDS[model]:
        word=unicodedata.normalize("NFKC",word).casefold()
        if word.isascii():
            if re.search(r'(?<![a-z0-9_])'+re.escape(word)+r'(?![a-z0-9_])',s):return True
        elif word in s:return True
    return False


def numbered_entries(html: str, model: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "nav", "footer"]):
        node.decompose()
    found = {}
    lines = list(soup.get_text("\n", strip=True).splitlines())
    # Some photo catalogues nest individual list entries inside blockquotes or
    # display them as inline spans: parse each structural item as a fallback.
    lines.extend(el.get_text(" ", strip=True) for el in soup.select("li,p,blockquote,tr"))
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        match = NUMBERED.search(line)
        if not match:
            continue
        number = int(match.group(1))
        if number < 1 or number > 250:
            continue
        title = match.group(2).strip(" -:·")
        # A URL named /yui/ can list an entire mixed-model publisher.
        # Require identity in this entry, not elsewhere on the page.
        if NUMBERED.search(title):continue
        prefix=line[:match.start()].strip()
        if not (relevant(title,model) or (len(prefix)<=40 and relevant(prefix,model))):
            continue
        if len(title) < 4 or len(title) > 180:
            continue
        count = PHOTOS.search(title)
        item = {"number": number, "title": title,
                "advertised_photos": int(count.group(1)) if count else None}
        if number not in found or len(title) > len(found[number]["title"]):
            found[number] = item
    return list(found.values())


def portfolio_entries(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    host = urlsplit(page_url).hostname
    for anchor in soup.select("a[href]"):
        link = urljoin(page_url, anchor.get("href", ""))
        parsed = urlsplit(link)
        if (parsed.scheme != "https" or parsed.hostname != host
                or not parsed.path.startswith("/portfolio/")
                or parsed.username or parsed.password):
            continue
        title = anchor.get_text(" ", strip=True)
        if len(title) < 5:
            img = anchor.find("img")
            title = (img.get("alt", "") if img else "").strip()
        if not 5 <= len(title) <= 170:
            continue
        found[link.split("#")[0]] = {"title": title, "work_url": link.split("#")[0],
                                     "advertised_photos": None}
    return list(found.values())


def visible_portfolio_pages(html: str, current: str, root: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    origin = urlsplit(root)
    found = []
    for anchor in soup.select("a[href]"):
        link = urljoin(current, anchor.get("href", ""))
        page = urlsplit(link)
        if page.scheme != "https" or page.hostname != origin.hostname:
            continue
        if page.path != origin.path and not page.path.startswith(origin.path.rstrip("/") + "/page/"):
            continue
        if (not re.search(r"/page/\d+/?$", page.path)
                and not re.search(r"(?:page|paged)=\d+", page.query)):
            continue
        if link not in found:
            found.append(link)
    return found


def fetch_html(session: requests.Session, url: str, host: str, timeout: int) -> str:
    response = session.get(url, timeout=(8, timeout), allow_redirects=False)
    if response.status_code != 200:
        raise ValueError("HTTP_" + str(response.status_code))
    final = urlsplit(response.url)
    if final.scheme != "https" or final.hostname != host:
        raise ValueError("UNEXPECTED_REDIRECT")
    if len(response.content) > 3_000_000:
        raise ValueError("PAGE_TOO_LARGE")
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("NOT_HTML")
    return response.text


def discover_source(source: dict, session: requests.Session, timeout: int) -> dict:
    url, mode = source["url"], source["mode"]
    host = urlsplit(url).hostname
    row = {k: source[k] for k in ("id", "model", "region", "tier", "mode", "url")}
    row.update(status="unavailable", pages_checked=0, items=[], error=None)
    if urlsplit(url).scheme != "https" or not host:
        row["error"] = "INVALID_SOURCE_URL"
        return row
    try:
        pending = [url]
        visited = set()
        max_pages = min(5, int(source.get("max_pages", 1)))
        while pending and len(visited) < max_pages:
            link = pending.pop(0)
            if link in visited:
                continue
            try:
                html = fetch_html(session, link, host, timeout)
            except (requests.RequestException, ValueError) as page_error:
                row.setdefault("page_errors", []).append({
                    "url": link, "reason": type(page_error).__name__ + ": " + str(page_error)[:100]
                })
                if not visited:
                    raise
                # Continue along other explicitly linked publisher pages.
                continue
            visited.add(link)
            row["pages_checked"] = len(visited)
            if mode == "numbered":
                row["items"].extend(numbered_entries(html, source["model"]))
            elif mode == "portfolio":
                row["items"].extend(portfolio_entries(html, link))
                for next_link in visible_portfolio_pages(html, link, url):
                    if next_link not in visited and next_link not in pending:
                        pending.append(next_link)
            elif mode == "single":
                if not relevant(html, source["model"]):
                    raise ValueError("MODEL_IDENTITY_NOT_CONFIRMED")
                row["items"] = [{"title": source["title"],
                                 "work_url": link,
                                 "advertised_photos": source.get("advertised_photos")}]
            elif mode == "profile":
                if source["identity"].casefold() not in html.casefold():
                    raise ValueError("PROFILE_IDENTITY_NOT_CONFIRMED")
            elif mode == "reference":
                if not relevant(html, source["model"]):
                    raise ValueError("MODEL_IDENTITY_NOT_CONFIRMED")
            else:
                raise ValueError("UNKNOWN_MODE")
            if mode != "portfolio":
                break
        row["status"] = "inspected" if mode in ("profile", "reference") else (
            "parsed" if row["items"] else "visible_but_no_parsed_works")
        if row.get("page_errors"):
            row["status"] = "partial"
        # Site numbering is local, never use it to dedupe works across sites.
        row["items"] = list({(x.get("work_url") or str(x.get("number"))):
                             x for x in row["items"]}.values())
    except (requests.RequestException, ValueError, KeyError) as exc:
        row["error"] = type(exc).__name__ + ": " + str(exc)[:120]
        row["status"] = "partial" if row["pages_checked"] else "unavailable"
    return row


def stored_title_index(model: str) -> dict[str, list[dict]]:
    folder = APPS / (model + "-gallery")
    path = folder / "stored-albums.json"
    if not path.is_file():
        return {}
    stored = json.loads(path.read_text(encoding="utf-8"))
    out = defaultdict(list)
    for item in stored.get("albums", []):
        title, album_id = item.get("title", ""), item.get("id", "")
        key = normalized(title)
        if len(key) < 6:
            continue
        images = item.get("images", [])
        count = len(images) if isinstance(images, list) else images if isinstance(images, int) else 0
        out[key].append({"id": album_id, "title": title, "stored_public_photos": count})
    return dict(out)


def reconcile(sources: list[dict], indices: dict[str, dict]) -> list[dict]:
    candidates = {}
    for source in sources:
        for entry in source["items"]:
            key = normalized(entry["title"])
            # Do not merge highly generic work titles such as "Yui" or "Vol.1".
            if len(key) < 6:
                key = f"{source['id']}:{entry.get('number', entry.get('work_url', ''))}"
            identity = (source["model"], key)
            row = candidates.setdefault(identity, {
                "model": source["model"], "normalized_title": key,
                "title": entry["title"], "sources": [],
                "advertised_counts": [], "exact_stored_title_matches": [],
                "discovery_only_not_gallery": True})
            row["sources"].append({"id": source["id"], "url": entry.get("work_url") or source["url"],
                                   "tier": source["tier"], "site_number": entry.get("number")})
            if entry.get("advertised_photos") is not None:
                row["advertised_counts"].append({"source": source["id"],
                                                 "photos": entry["advertised_photos"]})
            if key in indices[source["model"]]:
                row["exact_stored_title_matches"] = indices[source["model"]][key]
    return sorted(candidates.values(), key=lambda x: (
        x["model"], not any(s["tier"] == "official" for s in x["sources"]),
        -len(x["sources"]), x["normalized_title"]))


def run(registry: dict, timeout=20, pause=0.5, session=None) -> dict:
    session = session or requests.Session()
    session.headers.update({"User-Agent": AGENT, "Accept": "text/html"})
    sources = []
    for source in registry["sources"]:
        result = discover_source(source, session, timeout)
        sources.append(result)
        print("GLOBAL_SOURCE", source["id"], result["status"],
              result["pages_checked"], len(result["items"]), flush=True)
        if pause:
            time.sleep(pause)
    indices = {model: stored_title_index(model) for model in ("yui", "mimmi")}
    leads = reconcile(sources, indices)
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "warning": "Discovery only. Public index entries, claimed page counts and owner-index metadata are NOT physically archived photographs. Only verified local/cloud images passing browser QA belong in the gallery.",
        "summary": {
            "sources_checked": len(sources),
            "sources_inspected_or_parsed": sum(s["status"] in ("parsed", "inspected") for s in sources),
            "regions": sorted(set(s["region"] for s in sources)),
            "catalogue_title_groups": len(leads),
            "groups_without_exact_public_stored_title_match":
                sum(not x["exact_stored_title_matches"] for x in leads),
            "new_photos_stored": 0, "gallery_images_added": 0,
        },
        "sources": sources, "leads": leads
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 40:
        parser.error("timeout must be 5..40 seconds")
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    assert registry["schema_version"] == 1
    assert all(s["model"] in ("yui", "mimmi") for s in registry["sources"])
    result = run(registry, timeout=args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("GLOBAL_SOURCE_SUMMARY", json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
