"""Bounded, keyless public search candidate discovery with official AppView proof.

This is a backup path for iOS browsers whose direct CORS search is blocked.
Never treat bsky.md's author/text/timestamp as authoritative: only its public
post link is accepted, and then official getProfiles/getPosts resolves/verifies
the exact DID/URI/body. No credentials, private data or local persistence.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter()
TERMS = frozenset(("뒷계", "섹트", "섹블", "일탈계"))
SEARCH = "https://bsky.md/search"
PROFILES = "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles"
POSTS = "https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts"
LINK = re.compile(r"https://bsky\.app/profile/([a-z0-9][a-z0-9.-]{2,252})/post/([a-z0-9]{6,32})\b", re.I)
DID = re.compile(r"did:(?:plc|web):[a-zA-Z0-9._:%-]{8,200}\Z")
_LOCK = asyncio.Lock()
_CACHE: dict[tuple[str, str, str], tuple[float, list[dict]]] = {}


def _get_json(url: str) -> dict:
    req = Request(url, headers={"Accept": "application/json",
                                  "User-Agent": "INTERSECTION-public-reader/1.0"})
    with urlopen(req, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise ValueError("upstream unavailable")
        body = response.read(1_500_001)
        if len(body) > 1_500_000:
            raise ValueError("oversized API")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("invalid API")
    return parsed


def _query(term: str, start: str, end: str) -> list[dict]:
    search = SEARCH + "?" + urlencode({"q": term, "since": start, "until": end,
                                        "limit": "25"})
    req = Request(search, headers={"Accept": "text/markdown",
                                   "User-Agent": "INTERSECTION-public-reader/1.0"})
    with urlopen(req, timeout=12) as response:
        if not 200 <= response.status < 300:
            raise ValueError("search unavailable")
        source = response.read(400_001)
        if len(source) > 400_000:
            raise ValueError("oversized search")
    text = source.decode("utf-8", "replace")
    candidates: dict[tuple[str, str], None] = {}
    for handle, rkey in LINK.findall(text):
        handle = handle.lower()
        if ".." in handle or "." not in handle or handle.startswith(".") or handle.endswith("."):
            continue
        candidates[(handle, rkey.lower())] = None
        if len(candidates) >= 25:
            break
    if not candidates:
        return []
    actors = list(dict.fromkeys(h for h, _ in candidates))
    profile_url = PROFILES + "?" + urlencode([("actors", h) for h in actors])
    data = _get_json(profile_url)
    dids = {
        str(p.get("handle", "")).lower(): str(p.get("did"))
        for p in (data.get("profiles") or [])
        if isinstance(p, dict) and DID.fullmatch(str(p.get("did", "")))
    }
    uris = {
        "at://" + dids[handle] + "/app.bsky.feed.post/" + rkey
        for handle, rkey in candidates if dids.get(handle)
    }
    if not uris:
        return []
    post_url = POSTS + "?" + urlencode([("uris", u) for u in sorted(uris)])
    originals = _get_json(post_url)
    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    result = []
    for p in originals.get("posts") or []:
        if not isinstance(p, dict) or p.get("uri") not in uris:
            continue
        uri = str(p["uri"])
        author = p.get("author") or {}
        record = p.get("record") or {}
        if not isinstance(author, dict) or not isinstance(record, dict) or (
            not uri.startswith("at://" + str(author.get("did", "")) + "/")
        ):
            continue
        body = record.get("text")
        if not isinstance(body, str) or term not in body:
            continue
        created = record.get("createdAt", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                continue
            if not start_dt <= dt <= end_dt:
                continue
        except (TypeError, ValueError, AttributeError):
            continue
        result.append(p)
    return result[:25]


@router.get("/api/public-search-verified", include_in_schema=False)
async def public_search_verified(
    q: str = Query(..., min_length=2, max_length=16),
    since: str = Query(..., min_length=10, max_length=10),
    until: str = Query(..., min_length=10, max_length=10),
):
    if q not in TERMS:
        raise HTTPException(400, "Unsupported public search term")
    try:
        d1 = date.fromisoformat(since)
        d2 = date.fromisoformat(until)
    except ValueError:
        raise HTTPException(400, "Invalid date") from None
    today = datetime.now(timezone.utc).date()
    if d2 <= d1 or (d2 - d1).days > 31 or d1 < today - timedelta(days=35) or d2 > today + timedelta(days=2):
        raise HTTPException(400, "Date range exceeds public lookup bounds")
    key = (q, since, until)
    async with _LOCK:
        cached = _CACHE.get(key)
        if cached and time.monotonic() - cached[0] < 90:
            return JSONResponse({"verified": cached[1], "source": "official_appview",
                                 "partial": True, "cache": "recent"},
                                headers={"Cache-Control": "no-store"})
        try:
            verified = await asyncio.wait_for(
                asyncio.to_thread(_query, q, since, until), timeout=36)
        except Exception:
            return JSONResponse({"verified": [], "partial": True,
                                 "error": "upstream_unavailable"},
                                status_code=503, headers={"Cache-Control": "no-store"})
        if len(_CACHE) > 16:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), verified)
        return JSONResponse({"verified": verified, "source": "official_appview",
                             "partial": True, "cache": "fresh"},
                            headers={"Cache-Control": "no-store"})
