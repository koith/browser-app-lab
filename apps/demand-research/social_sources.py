"""Authorized, bounded public social search for the private INTERSECTION gateway.

No login bypasses, proxy rotation, scraping, persistent records or media downloads.
Provider keys are server-only and each interactive request fetches one page.
"""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import ipaddress, json, os, re, unicodedata

TERMS = ("뒷계", "섹트", "섹블", "일탈계")
ROUTES = {
    "x": "/v1/twitter/search/tweets",
    "threads": "/v1/threads/search",
    "instagram": "/v1/instagram/search/reels",
    "reddit": "/v1/reddit/search",
}
HOSTS = {
    "x": ("x.com", "twitter.com"),
    "threads": ("threads.net", "threads.com"),
    "instagram": ("instagram.com",),
    "reddit": ("reddit.com", "redd.it"),
}
BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


def https_url(value: object, hosts: tuple[str, ...] | None = None) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return ""
        if host in BLOCKED_HOSTS or host.endswith((".local", ".internal")):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        if re.match(r"^(?:127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.)", host):
            return ""
        if hosts and not any(host == h or host.endswith("." + h) for h in hosts):
            return ""
        return value
    except (TypeError, ValueError):
        return ""


def parsed_date(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / (1000 if value>10_000_000_000 else 1), timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str:
    return str(value)[:30000] if isinstance(value, str) else ""


def normalize_item(item: object, platform: str, term: str, start: datetime, end: datetime) -> dict | None:
    if platform not in ROUTES or term not in TERMS or not isinstance(item, dict):
        return None
    p = _dict(item.get("post")) or item
    author = _dict(p.get("author")) or _dict(item.get("author"))
    content = _dict(p.get("content"))
    ext = _dict(p.get("ext"))
    text = "\n".join(x for x in (
        _text(p.get("title") or ext.get("title")), _text(content.get("text")), _text(ext.get("selftext"))
    ) if x).strip()
    if not text or unicodedata.normalize("NFKC", term) not in unicodedata.normalize("NFKC", text):
        return None
    url = https_url(p.get("url"), HOSTS[platform])
    if not url:
        return None
    posted = parsed_date(p.get("published_at") or p.get("created_at")
                         or p.get("timestamp") or p.get("createdAt"))
    if not posted or posted < start or posted >= end:
        return None
    uid = str(p.get("id") or "").strip()
    if not uid or len(uid) > 140:
        return None
    handle = _text(author.get("username") or author.get("handle")).lstrip("@")
    handle = handle[:100]
    profile = https_url(author.get("url") or author.get("profile_url"), HOSTS[platform])
    if not profile and re.fullmatch(r"[A-Za-z0-9_.]{1,60}", handle):
        profile = {
            "x": f"https://x.com/{handle}",
            "threads": f"https://www.threads.com/@{handle}",
            "instagram": f"https://www.instagram.com/{handle}/",
            "reddit": f"https://www.reddit.com/user/{handle}/",
        }[platform]
    if not profile:
        return None
    media = []
    urls = content.get("media_urls") or ext.get("all_media_urls") or []
    if isinstance(urls, str):
        urls = [urls]
    thumb = https_url(content.get("thumbnail_url"))
    if isinstance(urls, list):
        for value in urls[:12]:
            media_url = https_url(value)
            if media_url:
                media.append({
                    "type": "video" if re.search(r"\.(mp4|m3u8|webm)(?:[?#]|$)", media_url, re.I) else "image",
                    "url": media_url, "thumb": thumb or media_url, "alt": "공개 게시글 첨부",
                })
    if not media and thumb:
        media.append({"type": "image", "url": thumb, "thumb": thumb, "alt": "공개 썸네일"})
    flags = _dict(p.get("flags"))
    return {
        "id": f"{platform}:{uid}", "platform": platform,
        "author": _text(author.get("display_name") or author.get("name") or handle or "작성자")[:120],
        "profileUrl": profile, "url": url, "text": text,
        "posted": posted.isoformat(), "indexed": posted.isoformat(),
        "media": media, "adultLabeled": bool(flags.get("nsfw")),
        "restricted": bool(flags.get("deleted") or flags.get("private")),
    }


def parse_response(body: dict, platform: str, term: str, start: datetime, end: datetime) -> dict:
    if not isinstance(body, dict) or body.get("success") is not True:
        raise ValueError("upstream_unsuccessful")
    data = _dict(body.get("data"))
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("upstream_schema_invalid")
    rows, seen = [], set()
    for item in items[:100]:
        row = normalize_item(item, platform, term, start, end)
        if row and row["id"] not in seen and not row["restricted"]:
            seen.add(row["id"])
            rows.append(row)
    page = _dict(body.get("pagination"))
    return {
        "platform": platform, "term": term, "items": rows,
        "received": len(items), "accepted": len(rows),
        "next_cursor": page.get("next_cursor") if page.get("has_more") is True else None,
        "has_more": page.get("has_more") is True,
        "empty_reason": str(data.get("empty_reason") or "")[:80],
        "credits_used": body.get("credits_used") if isinstance(body.get("credits_used"), int) else None,
        "provider": "socialcrawl", "verified_live": True,
    }


def request_one_page(key: str, platform: str, term: str, start: datetime, end: datetime, cursor: str = "") -> dict:
    if platform not in ROUTES or term not in TERMS:
        raise ValueError("invalid_query")
    if len(key) < 12:
        raise ValueError("missing_key")
    params = {"query": term}
    if platform == "x":
        params.update({"sort": "latest", "since": start.date().isoformat(), "until": end.date().isoformat()})
    if platform == "threads":
        params.update({"start_date": start.date().isoformat(), "end_date": end.date().isoformat(), "expand": "false"})
    if platform == "instagram":
        params.update({"date_posted": "last-month"})
    if platform == "reddit":
        params.update({"sort": "new"})
    if cursor:
        if len(cursor) > 900:
            raise ValueError("invalid_cursor")
        params["cursor"] = cursor
    path = ROUTES[platform]
    url = "https://www.socialcrawl.dev" + path + "?" + urlencode(params)
    req = Request(url, headers={"x-api-key": key, "Accept": "application/json",
                                "User-Agent": "IntersectionPrivateResearch/1.0"})
    try:
        with urlopen(req, timeout=25) as response:
            if response.status != 200:
                raise ValueError("upstream_http")
            raw = response.read(1_500_001)
            if len(raw) > 1_500_000:
                raise ValueError("upstream_response_too_large")
            body = json.loads(raw)
    except HTTPError as error:
        raise ValueError("upstream_http_" + str(error.code)) from None
    except (URLError, TimeoutError):
        raise ValueError("upstream_network_error") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("upstream_json_invalid") from None
    return parse_response(body, platform, term, start, end)
