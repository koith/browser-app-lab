"""Explicitly self-declared public-account connections, not person identification.

A link can contribute to a group only when BOTH account owners placed an
explicit cross-account link on their official public profiles. Never infer a
connection from handles, writing style, timing, follower graph or photographs.
No profile description or post text is stored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import account_index

EVIDENCE_TTL = 14 * 86400
LINK_RE = re.compile(r"https://[^\s<>\"'\x00-\x1f]{1,512}", re.I)
# Explicit self-account disclosure, not simply a link to a friend or promotion.
SELF_LINK = re.compile(
    r"(?:my\s+(?:other|alt|alternate|second|backup)\s+(?:account|profile)"
    r"|also\s+me\s+(?:on|at)"
    r"|(?:내|제)\s*(?:다른|부|보조|서브)\s*계정"
    r"|(?:나의|제)\s*(?:계정|SNS)\s*목록"
    r"|(?:본인|같은\s*사람)의\s*(?:다른|부)\s*계정)",
    re.I,
)
PUBLIC_HOSTS = (
    "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles",
    "https://api.bsky.app/xrpc/app.bsky.actor.getProfiles",
)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and isinstance(value, str):
                self.hrefs.append(value)


def declared_accounts(description: str, *, html: str = "") -> list[str]:
    """Return canonical links only when text explicitly declares self-ownership.

    Mastodon HTML field labels are inspected separately from the href so a
    promotional third-party link never becomes an ownership assertion.
    """
    if not isinstance(description, str) or len(description) > 30000:
        return []
    if not SELF_LINK.search(description):
        return []
    matches = LINK_RE.findall(description)
    if html:
        parser = Links()
        parser.feed(html[:30000])
        matches.extend(parser.hrefs)
    result = set()
    for raw in matches[:80]:
        candidate = account_index.profile_url(raw.rstrip(".,;!?)]}"))
        if candidate:
            result.add(candidate[1])
    return sorted(result)


def ensure(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS account_self_links (
            src TEXT NOT NULL REFERENCES accounts(url) ON DELETE CASCADE,
            dst TEXT NOT NULL REFERENCES accounts(url) ON DELETE CASCADE,
            checked_at INTEGER NOT NULL,
            method TEXT NOT NULL CHECK(method='public_self_declaration'),
            PRIMARY KEY(src,dst)
        );
        CREATE INDEX IF NOT EXISTS ix_account_self_links_dst
            ON account_self_links(dst);
        CREATE TABLE IF NOT EXISTS account_profile_checks (
            url TEXT PRIMARY KEY REFERENCES accounts(url) ON DELETE CASCADE,
            checked_at INTEGER NOT NULL
        );
    """)


def replace_claims(db_path, source, targets, *, when=None):
    parsed = account_index.profile_url(source)
    if parsed is None:
        raise ValueError("Invalid source profile")
    if not isinstance(targets, (list, tuple, set)) or len(targets) > 100:
        raise ValueError("Invalid claim list")
    now = int(time.time()) if when is None else int(when)
    normalized = {
        p[1] for raw in targets if (p := account_index.profile_url(raw)) is not None
        and p[1] != parsed[1]
    }
    db = account_index.connect(db_path)
    try:
        ensure(db)
        with db:
            if db.execute("SELECT 1 FROM accounts WHERE url=?", (parsed[1],)).fetchone() is None:
                return {"updated": False, "links": 0}
            db.execute("DELETE FROM account_self_links WHERE src=?", (parsed[1],))
            # Only already indexed source accounts may appear in a group. Unknown
            # URLs cannot be manufactured into accounts by a profile description.
            allowed = {
                url for (url,) in db.execute(
                    "SELECT url FROM accounts WHERE url IN (%s)" % ",".join("?" for _ in normalized),
                    tuple(sorted(normalized)),
                ).fetchall()
            } if normalized else set()
            db.executemany(
                "INSERT INTO account_self_links(src,dst,checked_at,method) VALUES(?,?,?,'public_self_declaration')",
                ((parsed[1], url, now) for url in sorted(allowed)),
            )
            db.execute(
                """INSERT INTO account_profile_checks(url,checked_at) VALUES(?,?)
                   ON CONFLICT(url) DO UPDATE SET checked_at=excluded.checked_at""",
                (parsed[1],now),
            )
        return {"updated": True, "links": len(allowed)}
    finally:
        db.close()


def _connected_components(db, *, now=None):
    ensure(db)
    now = int(time.time()) if now is None else int(now)
    all_urls = [row[0] for row in db.execute("SELECT url FROM accounts")]
    parent = {url: url for url in all_urls}

    def root(url):
        while parent[url] != url:
            parent[url] = parent[parent[url]]
            url = parent[url]
        return url

    def union(a, b):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # Re-evaluate both sides; a one-direction promotional link is not proof.
    rows = db.execute(
        """SELECT a.src,a.dst FROM account_self_links a
           JOIN account_self_links b ON b.src=a.dst AND b.dst=a.src
           WHERE a.checked_at >= ? AND b.checked_at >= ?""",
        (now-EVIDENCE_TTL, now-EVIDENCE_TTL),
    ).fetchall()
    for src, dst in rows:
        if src in parent and dst in parent:
            union(src, dst)
    groups = {}
    for url in all_urls:
        groups.setdefault(root(url), []).append(url)
    return [sorted(members) for members in groups.values() if len(members) >= 2]


def groups_page(db_path, *, offset=0, limit=30, now=None):
    if not (0 <= offset <= 10000000 and 1 <= limit <= 100):
        raise ValueError("Invalid pagination")
    db = account_index.connect(db_path)
    try:
        groups = sorted(_connected_components(db, now=now), key=lambda m: (-len(m), m[0]))
        all_count = db.execute("SELECT count(*) FROM accounts").fetchone()[0]
        result = []
        for members in groups[offset:offset+limit]:
            placeholders = ",".join("?" for _ in members)
            posts, activity_days = db.execute(
                """SELECT count(DISTINCT post_hash),
                   count(DISTINCT CASE
                     WHEN posted_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*'
                     THEN substr(posted_at,1,10) END)
                   FROM observed WHERE account_url IN ("""+placeholders+")",
                members,
            ).fetchone()
            per_account = {
                url: (platform, count) for url, platform, count in db.execute(
                    """SELECT a.url,a.platform,count(DISTINCT o.post_hash)
                       FROM accounts a LEFT JOIN observed o ON o.account_url=a.url
                       WHERE a.url IN (""" + placeholders + ") GROUP BY a.url,a.platform",
                    members,
                ).fetchall()
            }
            key = hashlib.sha256("\n".join(members).encode()).hexdigest()[:16]
            result.append({
                "group_id": "A-"+key,
                "evidence": "reciprocal_explicit_public_self_declaration",
                "label": "공개적으로 연결을 선언한 계정 그룹",
                "account_count": len(members),
                "distinct_posts": posts,
                "capped_daily_contributions": activity_days,
                "contribution_rule": "at_most_one_group_contribution_per_utc_day",
                "accounts": [
                    {"profileUrl":url,"platform":per_account[url][0],"verified_posts":per_account[url][1]}
                    for url in members
                ],
            })
        grouped = sum(len(g) for g in groups)
        return {
            "total": len(groups),
            "offset": offset, "limit": limit,
            "linked_accounts": grouped,
            "unresolved_accounts": all_count-grouped,
            # Links may describe branding/team relationships; this must NOT be
            # published as the number of distinct humans.
            "distinct_people_verified": False,
            "deduplicated_account_units": len(groups)+(all_count-grouped),
            "account_count": all_count,
            "items": result,
        }
    finally:
        db.close()


def fetch_profiles(profiles):
    if len(profiles) > 25:
        raise ValueError("Batch exceeds public API bound")
    args = urlencode([("actors", actor) for actor in profiles])
    for host in PUBLIC_HOSTS:
        try:
            request = Request(host+"?"+args, headers={"Accept": "application/json"})
            with urlopen(request,timeout=10) as response:
                raw = response.read(500001)
            if len(raw)>500000:
                raise ValueError("Oversize response")
            data = json.loads(raw)
            if isinstance(data,dict) and isinstance(data.get("profiles"),list):
                return data["profiles"]
        except Exception:
            continue
    raise RuntimeError("Official public profile API unavailable")


def fetch_mastodon_profile(url):
    parsed = account_index.profile_url(url)
    if not parsed or parsed[0]!="mastodon":
        raise ValueError("Unsupported profile")
    from urllib.parse import urlsplit
    p = urlsplit(parsed[1])
    acct = p.path[2:]
    request = Request(p.scheme+"://"+p.netloc+"/api/v1/accounts/lookup?"+urlencode({"acct":acct}),
        headers={"Accept":"application/json"})
    with urlopen(request,timeout=10) as response:
        data=json.loads(response.read(500001))
    if not isinstance(data,dict) or data.get("locked") or data.get("suspended"):
        return []
    # Fields are self-description only when the field NAME says 'my other account'.
    results=[]
    fields=data.get("fields") if isinstance(data.get("fields"),list) else []
    for field in fields[:10]:
        if not isinstance(field,dict):
            continue
        name=str(field.get("name") or "")
        value=str(field.get("value") or "")
        results.extend(declared_accounts(name+" "+value,html=value))
    # Unstructured bio does not certify that a URL is self-owned.
    return sorted(set(results))


def scan_known_profiles(db_path, *, max_profiles=55, now=None,
                        bsky_fetch=fetch_profiles, mastodon_fetch=fetch_mastodon_profile):
    if not 1<=max_profiles<=80:
        raise ValueError("Invalid scan budget")
    now = int(time.time()) if now is None else int(now)
    db = account_index.connect(db_path)
    try:
        ensure(db)
        # Deterministic rotation of eligible profiles; failures never erase old claims.
        rows = db.execute("""
            SELECT a.url,a.platform FROM accounts a
            WHERE a.platform IN ('bluesky','mastodon')
            ORDER BY COALESCE((SELECT c.checked_at FROM account_profile_checks c WHERE c.url=a.url),0), a.url
            LIMIT ?""", (max_profiles,)).fetchall()
    finally:
        db.close()
    found,checked,failed = 0,0,0
    bluesky = [url for url,platform in rows if platform=="bluesky"]
    mastodon = [url for url,platform in rows if platform=="mastodon"]
    for i in range(0,len(bluesky),25):
        batch = bluesky[i:i+25]
        try:
            profiles = bsky_fetch([url.split("/profile/",1)[1] for url in batch])
            lookup={}
            for p in profiles:
                if not isinstance(p,dict) or p.get("labels") and any(
                    isinstance(x,dict) and x.get("val") in ("!hide","!takedown","!no-unauthenticated")
                    for x in p["labels"]):
                    continue
                for key in ("did","handle"):
                    if isinstance(p.get(key),str):
                        lookup[p[key].lower()]=p
            for url in batch:
                actor=url.split("/profile/",1)[1]
                item=lookup.get(actor)
                if item is None:
                    failed+=1
                    continue
                targets=declared_accounts(str(item.get("description") or ""))
                result=replace_claims(db_path,url,targets,when=now)
                found+=result["links"]
                checked+=1
        except Exception:
            failed+=len(batch)
    for url in mastodon:
        try:
            result=replace_claims(db_path,url,mastodon_fetch(url),when=now)
            found+=result["links"]
            checked+=1
        except Exception:
            failed+=1
    return {"checked":checked,"failed":failed,"public_claims":found,
            "groups":groups_page(db_path,limit=1,now=now)["total"],
            "interpretation":"mutually_self_declared_profiles_not_real_person_identification"}
