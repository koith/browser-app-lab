"""Private INTERSECTION account index: source-level dedup, incremental ingestion, no text archive.

Only the authenticated gateway opens the database. Browser clients cannot write
accounts. A profile is an SNS account, NOT an inferred natural person.
"""
from __future__ import annotations
import hashlib
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

KNOWN = {"bluesky", "x", "threads", "instagram", "mastodon", "misskey", "reddit", "lemmy"}
MASTODON = {"mastodon.social", "planet.moe", "twingyeo.kr"}
MISSKEY = {"misskey.io", "hoto.moe"}
PROFILE_LIMIT = 512


def profile_url(raw):
    if not isinstance(raw, str) or len(raw) > PROFILE_LIMIT:
        return None
    try:
        p = urlsplit(raw)
        if p.scheme != "https" or p.username or p.password or p.port or p.query or p.fragment:
            return None
        host = (p.hostname or "").lower().removeprefix("www.")
        path = unquote(p.path).rstrip("/")
        if "%" in path or "\\" in path or "//" in path:
            return None
        a = path.split("/")[1:] if path else []
    except (ValueError, UnicodeError):
        return None
    network = ""
    url = ""
    if host == "bsky.app" and len(a) == 2 and a[0] == "profile" and re.fullmatch(r"(?:did:(?:plc|web):[A-Za-z0-9.:-]{6,140}|[A-Za-z0-9][A-Za-z0-9.-]{2,199})", a[1]):
        network = "bluesky"
        url = "https://bsky.app/profile/" + a[1].lower()
    elif host in ("x.com", "twitter.com") and len(a) == 1 and re.fullmatch(r"[A-Za-z0-9_]{1,15}", a[0]) and a[0].lower() not in ("home", "search", "explore", "i", "login"):
        network = "x"
        url = "https://x.com/" + a[0].lower()
    elif host in ("threads.com", "threads.net") and len(a) == 1 and re.fullmatch(r"@[A-Za-z0-9._]{1,40}", a[0]):
        network = "threads"
        url = "https://www.threads.com/@" + a[0][1:].lower()
    elif host == "instagram.com" and len(a) == 1 and re.fullmatch(r"[A-Za-z0-9._]{1,30}", a[0]) and a[0].lower() not in ("p", "reel", "explore", "direct", "accounts"):
        network = "instagram"
        url = "https://www.instagram.com/" + a[0].lower() + "/"
    elif host in MASTODON and len(a) == 1 and re.fullmatch(r"@[A-Za-z0-9_.-]{1,60}", a[0]):
        network = "mastodon"
        url = "https://" + host + "/@" + a[0][1:].lower()
    elif host in MISSKEY and len(a) == 1 and re.fullmatch(r"@[A-Za-z0-9_.-]{1,60}", a[0]):
        network = "misskey"
        url = "https://" + host + "/@" + a[0][1:].lower()
    elif host == "reddit.com" and len(a) == 2 and a[0].lower() == "user" and re.fullmatch(r"[A-Za-z0-9_-]{3,20}", a[1]):
        network = "reddit"
        url = "https://www.reddit.com/user/" + a[1].lower() + "/"
    elif host == "lemmy.world" and len(a) == 2 and a[0] == "u" and re.fullmatch(r"[A-Za-z0-9_-]{3,50}", a[1]):
        network = "lemmy"
        url = "https://lemmy.world/u/" + a[1].lower()
    if not network:
        return None
    return (network, url)


def from_original(raw):
    """Infer only where the ORIGINAL permalink unambiguously contains the handle."""
    if not isinstance(raw, str) or len(raw) > 2048:
        return None
    try:
        p = urlsplit(raw)
        if p.scheme != "https" or p.username or p.password or p.port:
            return None
        host = (p.hostname or "").lower().removeprefix("www.")
        a = p.path.strip("/").split("/")
    except ValueError:
        return None
    url = ""
    if host in ("x.com", "twitter.com") and len(a) >= 3 and a[1] == "status" and re.fullmatch(r"[0-9]{8,25}", a[2]):
        url = "https://x.com/" + a[0]
    elif host == "bsky.app" and len(a) >= 4 and a[0] == "profile" and a[2] == "post":
        url = "https://bsky.app/profile/" + a[1]
    elif host == "reddit.com" and len(a) >= 2 and a[0].lower() == "user":
        url = "https://www.reddit.com/user/" + a[1] + "/"
    elif host in MASTODON and len(a) == 2 and a[0].startswith("@") and a[1].isdigit():
        url = "https://" + host + "/" + a[0]
    return profile_url(url)


def account_from_post(row):
    if not isinstance(row, dict) or row.get("restricted") is True:
        return None
    original = row.get("source_url") or row.get("url") or ""
    found = None
    for key in ("profile_url", "profileUrl", "author_profile_url", "author_url"):
        found = profile_url(row.get(key))
        if found:
            break
    if not found and isinstance(row.get("author"), dict):
        found = profile_url(row["author"].get("profile_url") or row["author"].get("url"))
    if not found:
        found = from_original(original)
    if not found:
        return None
    platform, url = found
    declared = str(row.get("platform", "")).lower()
    if declared and declared not in (platform, "twitter" if platform == "x" else platform):
        return None
    source_key = str(row.get("id") or original)
    if len(source_key) > 2048 or not source_key:
        return None
    identity = hashlib.sha256((platform + "\\0" + source_key).encode()).hexdigest()
    posted = str(row.get("posted_at") or row.get("posted") or "")[:36]
    return (url, platform, identity, posted)


def connect(db_path):
    if not isinstance(db_path, str) or not db_path or db_path == ":memory:":
        raise ValueError("Persistent private account DB path is required")
    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=25)
    db.execute("PRAGMA busy_timeout=25000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            url TEXT PRIMARY KEY, platform TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS observed (
            source TEXT NOT NULL, post_hash TEXT NOT NULL,
            account_url TEXT NOT NULL REFERENCES accounts(url),
            posted_at TEXT NOT NULL DEFAULT '',
            checked_at INTEGER NOT NULL,
            PRIMARY KEY (source, post_hash)
        );
        CREATE INDEX IF NOT EXISTS ix_observed_account ON observed(account_url);
        CREATE INDEX IF NOT EXISTS ix_account_platform ON accounts(platform);
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
    """)
    return db


def _upsert(db, items, source, now):
    count, skipped = 0, 0
    for row in items:
        parsed = account_from_post(row)
        if parsed is None:
            skipped += 1
            continue
        url, network, identity, posted = parsed
        db.execute("""INSERT INTO accounts(url,platform,updated_at) VALUES(?,?,?)
            ON CONFLICT(url) DO UPDATE SET updated_at=excluded.updated_at""", (url, network, now))
        db.execute("""INSERT INTO observed(source,post_hash,account_url,posted_at,checked_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(source,post_hash) DO UPDATE SET
            account_url=excluded.account_url,posted_at=excluded.posted_at,
            checked_at=excluded.checked_at""", (source,identity,url,posted,now))
        count += 1
    return count, skipped


def sync_catalog(db_path, posts):
    """Atomic full snapshot reconciliation: deletions in the catalog are removed."""
    if not isinstance(posts, list):
        raise ValueError("catalog posts must be a list")
    now = int(time.time())
    db = connect(db_path)
    try:
        with db:
            db.execute("CREATE TEMP TABLE incoming_hashes (hash TEXT PRIMARY KEY)")
            n, skipped = _upsert(db, posts, "catalog", now)
            hashes = []
            for row in posts:
                parsed = account_from_post(row)
                if parsed: hashes.append((parsed[2],))
            db.executemany("INSERT OR IGNORE INTO incoming_hashes VALUES(?)",hashes)
            db.execute("DELETE FROM observed WHERE source='catalog' AND post_hash NOT IN (SELECT hash FROM incoming_hashes)")
            db.execute("DELETE FROM accounts WHERE NOT EXISTS (SELECT 1 FROM observed WHERE observed.account_url=accounts.url)")
            db.execute("""INSERT INTO index_meta(key,value) VALUES('last_catalog_sync',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(str(now),))
            db.execute("""INSERT INTO index_meta(key,value) VALUES('last_catalog_skipped',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(str(skipped),))
        return {"accepted":n,"skipped":skipped}
    finally:
        db.close()



def ingest_verified_marker_page(db_path, posts, verified_ids, all_ids, cursor):
    """Merge one independently SHA-checked TeraBox journal page, append-only.

    A full catalog snapshot importer may remove entries absent from the new
    snapshot. A PARTIAL marker page must NEVER do that; verified previous
    observations remain intact across provider timeouts and reconnects.
    The cursor and verification receipts live inside the same private SQLite
    transaction as the imported rows.
    """
    pattern=re.compile(r"[a-f0-9]{40}\Z")
    if (not isinstance(posts,list) or len(posts)>24 or
            not isinstance(verified_ids,list) or len(verified_ids)>24 or
            not isinstance(all_ids,list) or len(all_ids)>150000 or
            len(set(all_ids))!=len(all_ids) or
            any(not isinstance(pid,str) or not pattern.fullmatch(pid)
                for pid in all_ids+verified_ids) or
            not set(verified_ids).issubset(set(all_ids)) or
            not isinstance(cursor,str) or
            (cursor and not pattern.fullmatch(cursor))):
        raise ValueError("invalid bounded private journal sync input")
    if any(not isinstance(post,dict) or post.get("id") not in verified_ids
           for post in posts):
        raise ValueError("catalog page must contain only SHA-verified markers")
    now=int(time.time())
    db=connect(db_path)
    try:
        with db:
            db.execute("""CREATE TABLE IF NOT EXISTS verified_archive_markers(
                id TEXT PRIMARY KEY, verified_at INTEGER NOT NULL)""")
            accepted,skipped=_upsert(db,posts,"catalog",now)
            db.executemany("""INSERT INTO verified_archive_markers(id,verified_at)
                VALUES(?,?) ON CONFLICT(id) DO UPDATE SET
                verified_at=excluded.verified_at""",
                [(pid,now) for pid in verified_ids])
            db.execute("""INSERT INTO index_meta(key,value)
                VALUES('journal_page_cursor',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(cursor,))
            seen={r[0] for r in db.execute(
                "SELECT id FROM verified_archive_markers")}
            outstanding=len(set(all_ids)-seen)
            # Never set last_catalog_sync: a page is NOT full catalog parity.
        return {"accepted":accepted,"skipped":skipped,
                "current_marker_count":len(all_ids),
                "pending_marker_count":outstanding,
                "journal_marker_page_verified":len(verified_ids)}
    finally:
        db.close()



def ingest_discovery(db_path, posts):
    if not isinstance(posts,list) or len(posts)>100:
        raise ValueError("invalid provider batch")
    now=int(time.time())
    db=connect(db_path)
    try:
        with db:
            n, skipped=_upsert(db,posts,"discovery",now)
            db.execute("DELETE FROM observed WHERE source='discovery' AND checked_at < ?",(now-90*86400,))
            db.execute("DELETE FROM accounts WHERE NOT EXISTS (SELECT 1 FROM observed WHERE observed.account_url=accounts.url)")
        return {"accepted":n,"skipped":skipped}
    finally:
        db.close()


def status(db_path):
    db=connect(db_path)
    try:
        total=db.execute("SELECT count(*) FROM accounts").fetchone()[0]
        samples=db.execute("SELECT count(*) FROM observed").fetchone()[0]
        meta=dict(db.execute("SELECT key,value FROM index_meta").fetchall())
        source_counts=dict(db.execute("SELECT source,count(*) FROM observed GROUP BY source").fetchall())
        return {"accounts":total,"source_rows":samples,"sources":source_counts,
            "last_catalog_sync":int(meta.get("last_catalog_sync","0")),
            "last_catalog_skipped":int(meta.get("last_catalog_skipped","0")),
            "scope":"private_authorized_catalog_and_provider_pages",
            "coverage_complete":False,"same_person_inferred":False}
    finally:
        db.close()


def page(db_path,offset=0,limit=80,q="",platform=""):
    if not 0<=offset<=10_000_000 or not 1<=limit<=100:
        raise ValueError("invalid pagination")
    if len(q)>80 or platform and platform not in KNOWN:
        raise ValueError("invalid search")
    db=connect(db_path)
    try:
        where=["1=1"];args=[]
        if q:
            where.append("a.url LIKE ? ESCAPE '\\'")
            args.append("%"+q.lower().replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%")
        if platform:
            where.append("a.platform=?");args.append(platform)
        filt=" AND ".join(where)
        total=db.execute("SELECT count(*) FROM accounts a WHERE "+filt,args).fetchone()[0]
        rows=db.execute("""SELECT a.url,a.platform,count(DISTINCT o.post_hash) AS posts,
                max(o.posted_at) AS latest
                FROM accounts a JOIN observed o ON o.account_url=a.url WHERE """+filt+
                """ GROUP BY a.url,a.platform
                ORDER BY posts DESC,a.url ASC LIMIT ? OFFSET ?""",args+[limit,offset]).fetchall()
        return {"total":total,"offset":offset,"limit":limit,"items":[
            {"profileUrl":url,"platform":network,"verified_posts":count,"latest_posted":latest}
            for url,network,count,latest in rows]}
    finally:
        db.close()
