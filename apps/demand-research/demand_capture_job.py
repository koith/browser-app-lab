"""Frequent incremental capture of confirmed PUBLIC SNS originals to private TeraBox.

Runs on a scheduled private GitHub Actions runner. No scraped posts or media are
written to the public repository, build artifacts or workflow logs. This job
does not bypass logins/private account visibility and never promises complete
coverage of posts deleted between source polling passes.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

from demand_archive import CloudArchive, MIMES, canonical_json, post_key, public_url, sha256
from account_index_sources import fetch_public as bluesky_public_search

TERMS = ("뒷계", "섹트", "일탈계")
WINDOW_MINUTES = 16
MAX_PER_RUN = 90
MAX_MEDIA_PER_POST = 6
MAX_IMAGE = 24_000_000
MAX_VIDEO = 80_000_000
ALLOWED_MEDIA = (
    "cdn.bsky.app", "video.bsky.app", "files.mastodon.social",
    "media.misskey.io", "misskey.io", "hoto.moe", "pictrs.lemmy.world",
    "static.mstdn.social", "media.mstdn.social", "media.twingyeo.kr",
    "planet.moe", "twingyeo.kr", "media.planet.moe",
)
SENSITIVE_LABELS = {"!hide", "!takedown", "porn", "sexual", "nudity", "graphic-media"}
MIMES_LIMITS = {"image/jpeg": MAX_IMAGE, "image/png": MAX_IMAGE,
                "image/webp": MAX_IMAGE, "image/avif": MAX_IMAGE,
                "video/mp4": MAX_VIDEO, "video/webm": MAX_VIDEO,
                "video/quicktime": MAX_VIDEO}


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plaintext(raw):
    parser = TextOnly()
    parser.feed(str(raw or "")[:100000])
    return html.unescape(" ".join(parser.parts)).strip()


def at_date(raw, start, end):
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        ts = dt.timestamp()
        return dt.astimezone(timezone.utc).isoformat() if start <= ts <= end + 60 else None
    except (ValueError, TypeError, OverflowError):
        return None


def sensitive_labels(labels):
    if not isinstance(labels, list):
        return False
    return any(isinstance(x, dict) and
               str(x.get("val", "")).lower() in SENSITIVE_LABELS for x in labels)


def normalized(platform, original_id, url, text, published, media_urls=(), profile_url=''):
    if not public_url(url) or not isinstance(text, str) or not any(t in text for t in TERMS):
        return None
    text = text[:30000]
    media = [u for u in media_urls if isinstance(u, str) and public_url(u)]
    return {"platform": platform, "original_id": original_id,
            "source_url": url, "text": text, "posted_at": published,
            "profile_url": profile_url if public_url(profile_url) else "",
            "media_urls": list(dict.fromkeys(media))[:MAX_MEDIA_PER_POST],
            "media_expected": len(list(dict.fromkeys(media_urls)))}


def bluesky(term, start, end):
    body = bluesky_public_search(term, start, end)
    for item in body.get("posts", [])[:100]:
        try:
            rec = item.get("record") or {}
            author = item.get("author") or {}
            uri = item.get("uri") or ""
            match = re.fullmatch(
                r"at://(did:(?:plc|web):[A-Za-z0-9.:-]{6,150})/app\.bsky\.feed\.post/([A-Za-z0-9]+)", uri)
            if (not match or match.group(1) != author.get("did")
                    or sensitive_labels(item.get("labels"))
                    or sensitive_labels(author.get("labels"))):
                continue
            posted = at_date(rec.get("createdAt"), start, end)
            if not posted:
                continue
            embed = item.get("embed") or {}
            images = [m.get("fullsize") for m in embed.get("images", [])
                      if isinstance(m, dict)] if isinstance(embed, dict) else []
            link = "https://bsky.app/profile/" + match.group(1) + "/post/" + match.group(2)
            row = normalized("bluesky", uri, link, rec.get("text", ""), posted, images,
                             "https://bsky.app/profile/" + match.group(1))
            if row:
                yield row
        except (TypeError, ValueError, AttributeError):
            continue


def get_json(url, body=None):
    headers = {"Accept": "application/json", "User-Agent": "INTERSECTION-PublicResearch/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    data = canonical_json(body) if body is not None else None
    with urlopen(Request(url, data=data, headers=headers), timeout=12) as response:
        blob = response.read(3_000_001)
    if len(blob) > 3_000_000:
        raise ValueError("public source response too large")
    return json.loads(blob)


def mastodon(term, start, end):
    for host in ("mastodon.social", "planet.moe", "twingyeo.kr"):
        url = "https://" + host + "/api/v1/timelines/tag/" + quote(term) + "?limit=40"
        try:
            data = get_json(url)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict) or item.get("visibility") != "public" or item.get("sensitive"):
                continue
            if sensitive_labels(item.get("labels")):
                continue
            posted = at_date(item.get("created_at"), start, end)
            text = plaintext(item.get("content"))
            if not posted or not text:
                continue
            url = item.get("url") or item.get("uri")
            attachments = item.get("media_attachments") or []
            images = [m.get("url") for m in attachments if isinstance(m, dict)
                      and m.get("type") in ("image", "video", "gifv")]
            row = normalized("mastodon", str(item.get("uri") or item.get("id")), url,
                             text, posted, images, (item.get("account") or {}).get("url", ""))
            if row:
                yield row


def misskey(term, start, end):
    for host in ("misskey.io", "hoto.moe"):
        try:
            data = get_json("https://" + host + "/api/notes/search",
                            {"query": term, "limit": 50})
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for note in data:
            if not isinstance(note, dict) or note.get("visibility") != "public":
                continue
            if note.get("localOnly") or note.get("cw") or note.get("sensitive"):
                continue
            posted = at_date(note.get("createdAt"), start, end)
            user = note.get("user") or {}
            uid = str(user.get("username") or "")
            nid = str(note.get("id") or "")
            if not posted or not re.fullmatch(r"[A-Za-z0-9_.-]{1,70}", uid) or not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", nid):
                continue
            media = [m.get("url") for m in (note.get("files") or [])
                     if isinstance(m, dict) and not m.get("isSensitive")]
            link = "https://" + host + "/notes/" + nid
            row = normalized("misskey", host + ":" + nid, link,
                             str(note.get("text") or ""), posted, media,
                             "https://" + host + "/@" + uid)
            if row:
                yield row


def lemmy(term, start, end):
    try:
        data = get_json("https://lemmy.world/api/v3/search?" +
                        urlencode({"q": term, "type_": "Posts", "sort": "New", "limit": 40}))
    except Exception:
        return
    for item in data.get("posts", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        p = item.get("post") or {}
        if p.get("nsfw") or p.get("removed") or p.get("deleted"):
            continue
        posted = at_date(p.get("published"), start, end)
        if not posted:
            continue
        url = p.get("ap_id") or ""
        source = str(p.get("name") or "") + " " + str(p.get("body") or "")
        row = normalized("lemmy", str(p.get("id") or url), url, source,
                         posted, [p.get("thumbnail_url")] if p.get("thumbnail_url") else [])
        if row:
            yield row


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


MEDIA_OPENER = build_opener(NoRedirect())


def media_allowed(url):
    if not public_url(url):
        return False
    host = (urlsplit(url).hostname or "").lower()
    return host in ALLOWED_MEDIA


def download_media(url):
    if not media_allowed(url):
        return None
    try:
        request = Request(url, headers={"Accept": "image/*,video/*",
                                      "User-Agent": "INTERSECTION-PublicResearch/1.0"})
        with MEDIA_OPENER.open(request, timeout=12) as response:
            mime = response.headers.get("Content-Type", "").split(";")[0].lower().strip()
            limit = MIMES_LIMITS.get(mime, 0)
            if not limit:
                return None
            data = response.read(limit + 1)
            if not 0 < len(data) <= limit:
                return None
        return mime, data
    except Exception:
        return None


def make_post(row, now, get_media=download_media, pid_override=None, cloud=None):
    pid = pid_override or post_key(row["platform"], row["original_id"])
    sources = row["media_urls"]
    media = []
    blobs = []
    for index, url in enumerate(sources, start=1):
        item = get_media(url)
        if item is None and cloud is not None:
            # This slot may already contain the same original media from an
            # earlier partial attempt. Verify its private byte SHA before reuse.
            item = cloud.read_staged_media(pid,index)
        if item is None:
            continue
        mime, blob = item
        if mime not in MIMES or not isinstance(blob, bytes):
            continue
        # Stable original attachment positions: a missing first image must not
        # shift another post image into its slot in a future retry.
        key = "posts/" + pid + "/media/" + str(index).zfill(4) + MIMES[mime]
        media.append({"key": key, "mime": mime, "bytes": len(blob),
                      "sha256": sha256(blob), "remote_verified": True,
                      "kind": "video" if mime.startswith("video/") else "image"})
        blobs.append(blob)
    post = {"id": pid, "platform": row["platform"], "source_url": row["source_url"],
            "posted_at": row["posted_at"], "captured_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "text": row["text"], "profile_url": row.get("profile_url", ""), "media": media,
            "media_expected": row["media_expected"], "media_saved": len(media),
            "archive_complete": len(media) == row["media_expected"],
            "provenance": "public_source_observed", "retention_review": "required_on_removal_request"}
    return post, blobs


def public_error_class(err):
    """Strictly whitelisted aggregation. Never log post text/IDs/URLs/errors."""
    categories=(
        ("early original capture mismatch","first_observation_conflict"),
        ("immutable archive key collision","immutable_key_conflict"),
        ("immutable cloud write collision","remote_write_conflict"),
        ("private cloud readback did not converge","readback_mismatch"),
        ("parent directory unverified","backend_parent_unverified"),
        ("private cloud mkdir failed (missing)","backend_mkdir_missing"),
        ("private cloud copyto failed (missing)","backend_upload_missing"),
        ("private cloud rcat failed (missing)","backend_upload_missing"),
        ("after alternate methods","backend_write_unverified"),
        ("(rate_limited)","backend_rate_limit"),
        ("(duplicate)","backend_duplicate"),
        ("(authorization)","backend_authorization"),
        ("(missing)","backend_missing_path"),
        ("(network_timeout)","backend_timeout"),
        ("(capacity)","backend_capacity"),
        ("(remote_server)","backend_server_error"),
        ("(backend_rejected)","backend_rejected"),
        ("checksum","checksum_failure"),
        ("bad original media","media_integrity_failure")
    )
    chain=[]
    current=err
    for _ in range(4):
        if current is None:
            break
        chain.append(str(current).lower())
        current=current.__cause__
    # The outer message "write unverified" hides the useful safe error class
    # from the original rclone invocation. Prefer the root cause.
    for msg in reversed(chain):
        for pattern,name in categories:
            if pattern in msg:
                return name
    return "unclassified_failure"


def run(fetchers=None, cloud=None, clock=time.time, run_id=None, *, fast_mode=False):
    if os.environ.get("DEMAND_CAPTURE_PUBLIC_ALLOWED", "") != "1":
        raise RuntimeError("public capture needs explicit source/retention authorization")
    cloud = cloud or CloudArchive()
    cloud.preflight()
    now = int(clock())
    run_id = run_id or os.getenv("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[0-9]{6,30}", str(run_id)):
        raise ValueError("an immutable numeric run ID is required")
    start = now - WINDOW_MINUTES * 60
    sources = fetchers or (bluesky, mastodon, misskey, lemmy)
    saved = partial = duplicates = fetched = failures = storage_failures = 0
    storage_error_kinds={}
    capture_interrupted = False
    early_recovered = invalid_early_captures = failed_early_recoveries = recovered = 0
    if fast_mode:
        # Fast acquisition lists only existing names. The separate recovery job
        # verifies every journal entry's checksum.
        known={}
        known_ids=cloud.marker_ids()
    else:
        known = {p["id"]: p for p in cloud.load_catalog(include_entries=False)}
        known, recovered = cloud.recover_entries(known)
        early_recovered = 0
        invalid_early_captures = 0
        failed_early_recoveries = 0
        # Independent first-observation snapshots survive truncated/post-deletion
        # runs. A single damaged object must never poison the entire archive.
        for pid in cloud.pending_capture_ids(known)[:MAX_PER_RUN]:
            try:
                raw = cloud.read_first_observation(pid)
                if raw is None:
                    continue
                first = json.loads(raw)
                if (not isinstance(first, dict)
                        or first.get("id") != pid
                        or first.get("platform") not in
                        ("bluesky", "mastodon", "misskey", "lemmy")
                        or not isinstance(first.get("text"), str)
                        or not 0 <= len(first["text"]) <= 30_000
                        or not public_url(first.get("source_url"))
                        or not isinstance(first.get("posted_at"), str)
                        or not isinstance(first.get("observed_at"), int)
                        or not 1577836800 <= first["observed_at"] <= now+120
                        or not isinstance(first.get("media_links"), list)
                        or len(first["media_links"]) > MAX_MEDIA_PER_POST
                        or any(not public_url(link) for link in first["media_links"])):
                    raise ValueError("invalid original public capture record")
                row = {"platform": first["platform"], "source_url": first["source_url"],
                       "text": first["text"], "posted_at": first["posted_at"],
                       "profile_url": first.get("profile_url", ""),
                       "media_urls": first["media_links"],
                       "media_expected": len(first["media_links"])}
                post, blobs = make_post(row, first["observed_at"], pid_override=pid, cloud=cloud)
                if not post["archive_complete"]:
                    cloud.stage_partial_media(post,blobs)
                    # The immutable post.json would otherwise freeze a missing
                    # original attachment forever. Keep the early source snapshot
                    # pending and retry while the public original remains accessible.
                    failed_early_recoveries += 1
                    continue
            except (ValueError,TypeError,KeyError,OverflowError,json.JSONDecodeError):
                # Keep damaged bytes untouched. Do not promote or overwrite them.
                cloud.quarantined_ids.add(pid)
                invalid_early_captures += 1
                continue
            try:
                saved_post=cloud.save_post(post,blobs)
            except (RuntimeError,ValueError):
                # A recoverable network/backend failure is not an invalid source.
                failed_early_recoveries += 1
                continue
            known[pid]=saved_post
            early_recovered+=1
        known_ids=set(known)
    seen_this_scan = set()
    budget_exhausted = False
    for getter in sources:
        if budget_exhausted or capture_interrupted:
            break
        for term in TERMS:
            if budget_exhausted or capture_interrupted:
                break
            try:
                iterator = iter(getter(term, start, now))
            except Exception:
                failures += 1
                continue
            while True:
                try:
                    row = next(iterator)
                except StopIteration:
                    break
                except Exception:
                    # One provider may fail; retain records already captured
                    # and continue to other public providers and search terms.
                    failures += 1
                    break
                fetched += 1
                pid = post_key(row["platform"], row["original_id"])
                if pid in known_ids or pid in known or pid in seen_this_scan:
                    duplicates += 1
                    continue
                if saved >= (24 if fast_mode else MAX_PER_RUN):
                    budget_exhausted = True
                    break
                seen_this_scan.add(pid)
                phase="read_first_snapshot"
                try:
                    # First remote write contains observed public text, ahead of media fetch.
                    early = {"id": pid, "platform": row["platform"], "text": row["text"],
                             "source_url": row["source_url"], "posted_at": row["posted_at"],
                             "observed_at": now, "media_links": row["media_urls"],
                             "profile_url": row.get("profile_url", "")}
                    first_blob = cloud.read_first_observation(pid)
                    if first_blob is None:
                        # A stale 404 from a cloud backend can make a previously
                        # written immutable original look missing. On conflicting
                        # readback, inspect the earlier snapshot and never clobber it.
                        try:
                            phase="write_first_snapshot"
                            first_blob = cloud.save_first_observation(pid,canonical_json(early))
                        except RuntimeError:
                            first_blob = cloud.read_first_observation(pid)
                            if first_blob is None:
                                raise
                    first = json.loads(first_blob)
                    if (not isinstance(first, dict)
                            or first.get("id") != pid
                            or first.get("platform") != row["platform"]
                            or first.get("source_url") != row["source_url"]
                            or first.get("posted_at") != row["posted_at"]
                            or not isinstance(first.get("text"), str)
                            or not isinstance(first.get("observed_at"), int)
                            or not isinstance(first.get("media_links"), list)):
                        raise ValueError("early original capture mismatch; cannot silently replace")
                    row = {**row, "text": first["text"],
                           "posted_at": first["posted_at"],
                           "profile_url": first.get("profile_url", ""),
                           "media_urls": first["media_links"],
                           "media_expected": len(first["media_links"])}
                    phase="write_post_and_verify_media"
                    post, blobs = make_post(row, first["observed_at"], cloud=cloud)
                    if not post["archive_complete"]:
                        cloud.stage_partial_media(post,blobs)
                        partial += 1
                        # The verified first-observation record already remains
                        # in the cloud. Never finalize a permanently incomplete
                        # post.json and mark it as a full backup.
                        continue
                    saved_post = cloud.save_post(post, blobs)
                    known[pid] = saved_post
                    known_ids.add(pid)
                    saved += 1
                    partial += not saved_post["archive_complete"]
                except (RuntimeError,ValueError) as error:
                    # A single failure must not poison other verified posts.
                    # Only a fixed category, never raw backend output or a
                    # personal source link, appears in public workflow logs.
                    kind=public_error_class(error)
                    label=phase+":"+kind
                    storage_error_kinds[label]=storage_error_kinds.get(label,0)+1
                    storage_failures += 1
                    seen_this_scan.discard(pid)
                    if storage_failures >= 3:
                        capture_interrupted = True
                        break
                    continue
    # Per-post verified objects are durable independently of the final catalog.
    # Log counts BEFORE publishing so a catalog failure does not obscure which
    # individual objects passed remote SHA256 readback.
    print("PRIVATE_PER_POST_READBACK_CHECKPOINT",json.dumps({
        "new_verified":saved,"restored_entries":recovered,
        "restored_first_observations":early_recovered,
        "catalog_expected":len(known) if not fast_mode else None,
        "known_marker_name_hints":len(known_ids) if fast_mode else None,
        "integrity_excluded":cloud.unrecoverable_entries,
        "write_failures":storage_failures,
        "pending_media_retry":partial + failed_early_recoveries,
        "storage_error_categories":storage_error_kinds,
        "source_query_failures":failures,
        "invalid_early_captures":invalid_early_captures,
        "failed_early_recoveries":failed_early_recoveries,
        "capture_interrupted":capture_interrupted
    },sort_keys=True),flush=True)
    # Entries written immediately per post are the recovery journal. The versioned
    # catalog is published LAST and never destroys an earlier verified catalog.
    if fast_mode:
        catalog={"mode":"journal_fast_capture","catalog_sha256_verified":False,
                 "publication_pending":True,
                 "readable_via_verified_entry_journal":True,
                 "reason":"compact_catalog_rebuilt_by_separate_integrity_job"}
    elif saved or recovered or early_recovered:
        try:
            catalog = cloud.publish_catalog(known, run_id)
        except (RuntimeError,ValueError):
            # Verified per-post journal remains independently readable when
            # the optional compact index cannot be published.
            catalog = {"posts":len(known),"catalog_sha256_verified":False,
                       "publication_pending":True,
                       "readable_via_verified_entry_journal":True}
            print("::warning::Compact catalog publication deferred; verified post journal remains readable",flush=True)
    else:
        catalog = {"posts": len(known), "catalog_sha256_verified": False,
                   "reason": "no new items"}
    result = {"fetched": fetched, "saved_verified": saved, "partial_media": partial,
              "pending_media_retry": partial + failed_early_recoveries,
              "duplicates": duplicates, "recovered_entries": recovered, "recovered_early_snapshots": early_recovered,
              "repaired_archive_markers": cloud.repaired_entries,
              "unrecoverable_markers": cloud.unrecoverable_entries,
              "source_query_failures": failures,
              "invalid_early_captures":invalid_early_captures,
              "failed_early_recoveries":failed_early_recoveries,
              "budget_exhausted": budget_exhausted,
              "storage_failures": storage_failures,
               "storage_error_categories":storage_error_kinds,
              "storage_interrupted": capture_interrupted, "catalog": catalog,
              "operational_status": ("DEGRADED_STORAGE" if storage_failures else
                "DEGRADED_MEDIA" if partial or failed_early_recoveries else
                "JOURNAL_ONLY" if fast_mode else
                "DEGRADED_INDEX" if catalog.get("publication_pending") else "VERIFIED_POSTS"),
              "scope": "confirmed_public_only", "poll_minutes": 5,
              "completeness_guaranteed": False}
    print("DEMAND_CAPTURE_AGGREGATE_ONLY", json.dumps(result, ensure_ascii=False), flush=True)
    if storage_failures:
        raise RuntimeError("some private cloud writes remain unverified")
    return result


if __name__ == "__main__":
    run(fast_mode=os.environ.get("DEMAND_FAST_CAPTURE_MODE")=="1")
