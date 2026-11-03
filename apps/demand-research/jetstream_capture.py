"""Official Bluesky Jetstream v2: near-live PUBLIC creation event capture.

Reads only public app.bsky.feed.post commit creates; no login bypass, profile
enrichment, inference, nonpublic APIs, or raw sensitive workflow logs.
Durably checkpoints a cursor only after verified post/catalog publication.
GitHub Actions scheduling is best-effort; this is NOT an always-on listener.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from demand_archive import CloudArchive, canonical_json, post_key, public_url
from demand_capture_job import (
    TERMS, MAX_MEDIA_PER_POST, MAX_PER_RUN, sensitive_labels, normalized, make_post
)

HOST = "jetstream.us-east.bsky.network"
STREAM = "wss://" + HOST + "/xrpc/network.bsky.jetstream.subscribeEvents"
DID = re.compile(r"did:(?:plc|web):[A-Za-z0-9.:-]{6,150}")
RKEY = re.compile(r"[A-Za-z0-9]{6,100}")
CID = re.compile(r"baf[A-Za-z0-9]{15,150}")
CURSOR_NAME = re.compile(r"cursor-([0-9]{6,30})\.json")


def event_row(envelope, since, until):
    if not isinstance(envelope, dict) or envelope.get("$type") != "message":
        return None
    ev = envelope.get("payload") or {}
    if (ev.get("$type") != "network.bsky.jetstream.subscribeEvents#commit"
            or ev.get("collection") != "app.bsky.feed.post"
            or ev.get("operation") != "create"):
        return None
    did, rkey, record = ev.get("did"), ev.get("rkey"), ev.get("record")
    if not (isinstance(did, str) and DID.fullmatch(did)
            and isinstance(rkey, str) and RKEY.fullmatch(rkey)
            and isinstance(record, dict)
            and record.get("$type") == "app.bsky.feed.post"):
        return None
    labels = record.get("labels")
    if isinstance(labels, dict):
        labels = labels.get("values")
    if sensitive_labels(labels):
        return None
    text = record.get("text")
    if not isinstance(text, str) or not any(term in text for term in TERMS):
        return None
    try:
        written = datetime.fromisoformat(str(record.get("createdAt", "")).replace("Z", "+00:00"))
        witness = datetime.fromisoformat(str(ev.get("time", "")).replace("Z", "+00:00"))
        if not written.tzinfo or not witness.tzinfo:
            return None
        # The event's witnessed time, not a client-controlled createdAt,
        # decides whether this is a recent public creation.
        if not since <= witness.timestamp() <= until + 60:
            return None
        if abs(written.timestamp() - witness.timestamp()) > 3600:
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    uri = "at://" + did + "/app.bsky.feed.post/" + rkey
    base = "https://bsky.app/profile/" + did
    images = []
    embed = record.get("embed") or {}
    if isinstance(embed, dict) and embed.get("$type") == "app.bsky.embed.images":
        for item in (embed.get("images") or [])[:MAX_MEDIA_PER_POST]:
            if not isinstance(item, dict) or not isinstance(item.get("image"), dict):
                continue
            blob = item["image"]
            cid = (blob.get("ref") or {}).get("$link") if isinstance(blob.get("ref"), dict) else None
            mime = str(blob.get("mimeType", ""))
            ext = {"image/jpeg": "jpeg", "image/png": "png",
                   "image/webp": "webp", "image/avif": "avif"}.get(mime)
            if isinstance(cid, str) and CID.fullmatch(cid) and ext:
                images.append("https://cdn.bsky.app/img/feed_fullsize/plain/"
                              + did + "/" + cid + "@" + ext)
    return normalized("bluesky", uri, base + "/post/" + rkey,
                      text, written.astimezone(timezone.utc).isoformat(),
                      images, profile_url=base)


def latest_cursor(cloud):
    names = [name for name in cloud.names("metadata/jetstream-cursors")
             if CURSOR_NAME.fullmatch(name)]
    for name in sorted(names, key=lambda n: int(CURSOR_NAME.fullmatch(n).group(1)), reverse=True)[:10]:
        try:
            raw = cloud.read("metadata/jetstream-cursors/" + name, cap=1024, optional=True)
            obj = json.loads(raw) if raw else None
            if (isinstance(obj, dict) and obj.get("host") == HOST
                    and type(obj.get("seq")) is int and 0 < obj["seq"] < 2**64
                    and type(obj.get("at")) is int and time.time() - obj["at"] < 30*60):
                return obj["seq"]
        except (ValueError, RuntimeError, TypeError):
            continue
    # Jetstream also accepts unix-microsecond cursors to rewind the live tail.
    return int((time.time() - 15 * 60) * 1_000_000)


def store_event_row(cloud, known, row, now):
    pid = post_key(row["platform"], row["original_id"])
    if pid in known:
        return False, False
    early = {"id": pid, "platform": row["platform"], "text": row["text"],
             "source_url": row["source_url"], "posted_at": row["posted_at"],
             "profile_url": row.get("profile_url", ""),
             "observed_at": now, "media_links": row["media_urls"]}
    cloud.write_immutable("posts/" + pid + "/capture.json", canonical_json(early))
    post, blobs = make_post(row, now)
    cloud.save_post(post, blobs)
    known[pid] = post
    return True, not post["archive_complete"]


async def listen(cloud, run_id, duration=95, ws_factory=None, clock=time.time):
    import websockets
    if not re.fullmatch(r"[0-9]{6,29}", str(run_id)):
        raise ValueError("unsafe cursor checkpoint identifier")
    duration = max(10, min(180, int(duration)))
    known = {post["id"]: post for post in cloud.load_catalog()}
    known, restored = cloud.recover_entries(known)
    cursor = latest_cursor(cloud)
    url = STREAM + "?" + urlencode({
        "collections": "app.bsky.feed.post", "kinds": "commit",
        "cursor": cursor})
    started = clock()
    last_seq, seen, matched, saved, partial, skipped = 0, 0, 0, 0, 0, 0
    factory = ws_factory or websockets.connect
    async with factory(url, subprotocols=["xrpc.v1.json"],
                       open_timeout=15, ping_interval=20, max_size=2_500_000) as ws:
        while clock() - started < duration:
            try:
                blob = await asyncio.wait_for(ws.recv(), timeout=8)
            except asyncio.TimeoutError:
                continue
            if not isinstance(blob, str) or len(blob) > 2_500_000:
                skipped += 1
                continue
            try:
                envelope = json.loads(blob)
            except (ValueError, TypeError):
                skipped += 1
                continue
            ev = envelope.get("payload") if isinstance(envelope, dict) else None
            if not isinstance(ev, dict):
                continue
            seq = ev.get("seq")
            if type(seq) is int and 0 < seq < 2**64:
                last_seq = max(last_seq, seq)
            seen += 1
            row = event_row(envelope, clock() - 3600, clock())
            if row is None:
                continue
            matched += 1
            if saved >= 75:
                skipped += 1
                break
            added, incomplete = store_event_row(cloud, known, row, int(clock()))
            if added:
                saved += 1
                partial += incomplete
    # Entry marker is written per post, so any failure before this point
    # is recovered by the next scheduled job. Publish catalog before cursor.
    if saved or restored:
        cloud.publish_catalog(known, str(run_id) + "1")
    if last_seq:
        cloud.write_immutable("metadata/jetstream-cursors/cursor-" + str(run_id) + ".json",
            canonical_json({"host": HOST, "seq": last_seq, "at": int(clock())}))
    stats = {"events_seen": seen, "keyword_matches": matched,
             "new_posts_saved": saved, "partial_media": partial,
             "recovered_entries": restored, "skipped": skipped,
             "cursor_checkpointed": bool(last_seq), "continuous_uptime": False}
    print("JETSTREAM_PUBLIC_AGGREGATES", json.dumps(stats, sort_keys=True), flush=True)
    return stats


def main():
    if os.getenv("DEMAND_CAPTURE_PUBLIC_ALLOWED") != "1":
        raise RuntimeError("public capture authorization not enabled")
    cloud = CloudArchive()
    cloud.preflight()
    return asyncio.run(listen(cloud, os.environ.get("GITHUB_RUN_ID", ""),
                              duration=int(os.getenv("DEMAND_JETSTREAM_SECONDS", "95"))))


if __name__ == "__main__":
    main()
