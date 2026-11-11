"""Bounded keyless Bluesky account discovery and historical window backfill.

Requests only public searchPosts, observes source visibility, and persists
validated profile URLs and opaque post hashes via account_index. Never stores
post text, photographs, inferred cross-account identities or session tokens.
"""
from __future__ import annotations
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import account_index

# The public AppView search service can reject keyless search even while the
# public api.bsky.app search endpoint is available. Try both official hosts.
APIS=("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
      "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts")
TERMS=("뒷계","섹트","섹블","일탈계")
HOUR=3600
DAY=86400
LOOKBACK_DAYS=365
MAX_PER_REQUEST=100
MIN_WINDOW=HOUR


def _date(epoch):
    return datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_public(term,start,end):
    if term not in TERMS or end<=start or end-start>DAY:
        raise ValueError("invalid bounded search window")
    params=urlencode({"q":term,"sort":"latest","limit":MAX_PER_REQUEST,
        "since":_date(start),"until":_date(end)})
    failures=[]
    for api in APIS:
        request=Request(api+"?"+params,headers={"Accept":"application/json",
            "User-Agent":"Mozilla/5.0 (compatible; INTERSECTION-Public-Index/1.0)"})
        try:
            with urlopen(request,timeout=12) as response:
                payload=response.read(2_000_001)
            if len(payload)>2_000_000:
                raise ValueError("search response too large")
            result=json.loads(payload)
            if not isinstance(result,dict) or not isinstance(result.get("posts"),list):
                raise ValueError("unexpected search API response")
            return result
        except Exception as error:
            code=getattr(error,"code",None)
            failures.append("HTTP_"+str(code) if isinstance(code,int)
                else type(error).__name__)
    raise RuntimeError("public_search_unavailable:"+",".join(failures))


def validated_rows(body,term,start,end):
    if not isinstance(body,dict) or not isinstance(body.get("posts"),list) or term not in TERMS:
        raise ValueError("invalid response")
    accepted=[]
    for p in body["posts"][:MAX_PER_REQUEST]:
        if not isinstance(p,dict) or not isinstance(p.get("record"),dict):
            continue
        if p.get("labels") and any(x.get("val") in ("!hide","!takedown") for x in p["labels"] if isinstance(x,dict)):
            continue
        author=p.get("author") or {}
        uri=str(p.get("uri") or "")
        match=re.fullmatch(r"at://(did:(?:plc|web):[A-Za-z0-9.:-]{6,150})/app\.bsky\.feed\.post/([A-Za-z0-9]+)",uri)
        if not match or not isinstance(author,dict):
            continue
        did=str(author.get("did") or "")
        handle=str(author.get("handle") or "")
        if did!=match.group(1) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{2,199}",handle):
            continue
        text=p["record"].get("text") or ""
        if not isinstance(text,str) or term not in text:
            continue
        posted=p["record"].get("createdAt") or ""
        indexed=p.get("indexedAt") or posted
        try:
            dt=datetime.fromisoformat(str(indexed).replace("Z","+00:00"))
            stamp=dt.timestamp()
        except (TypeError,ValueError,OverflowError):
            continue
        if dt.tzinfo is None or not start<=stamp<end:
            continue
        accepted.append({"id":uri,"platform":"bluesky",
            "profile_url":"https://bsky.app/profile/"+did,
            "posted":str(posted)[:36],
            "source_url":"https://bsky.app/profile/"+did+"/post/"+match.group(2)})
    return accepted


def _ensure_queue(db):
    db.executescript("""
      CREATE TABLE IF NOT EXISTS public_index_windows(
        term TEXT NOT NULL, begin_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
        accepted INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(term,begin_ts,end_ts)
      );
      CREATE INDEX IF NOT EXISTS ix_public_index_pending
        ON public_index_windows(status,begin_ts);
    """)


def run_batch(db_path,fetcher=fetch_public,max_requests=6,now=None):
    if max_requests<1 or max_requests>8:
        raise ValueError("invalid request budget")
    now=int(now if now is not None else time.time())
    current=now//HOUR*HOUR
    db=account_index.connect(db_path)
    errors=0;requests=0;accepted=0;split=0
    try:
        _ensure_queue(db)
        previous=db.execute("SELECT value FROM index_meta WHERE key='last_public_scan'").fetchone()
        if previous and now-int(previous[0])<55*60:
            prior_errors=db.execute("""SELECT count(*) FROM public_index_windows
                WHERE status='pending' AND error<>''""").fetchone()[0]
            if not prior_errors:
                return {"requests":0,"accepted":0,"skipped_recent_run":True}
        # Always check the last complete hour on the public index.
        for term in TERMS:
            db.execute("""INSERT OR IGNORE INTO public_index_windows
                (term,begin_ts,end_ts) VALUES(?,?,?)""",(term,current-HOUR,current))
        # Work back a day at a time; split saturated windows until one hour.
        oldest=db.execute("SELECT min(begin_ts) FROM public_index_windows").fetchone()[0]
        day=current-DAY if oldest is None else (oldest//DAY*DAY)-DAY
        if day>=current-LOOKBACK_DAYS*DAY:
            for term in TERMS:
                db.execute("""INSERT OR IGNORE INTO public_index_windows
                    (term,begin_ts,end_ts) VALUES(?,?,?)""",(term,day,day+DAY))
        db.commit()
        # Recent windows first, then older windows; retry failed windows at next run.
        pending=db.execute("""SELECT term,begin_ts,end_ts,attempts FROM public_index_windows
            WHERE status='pending' ORDER BY (begin_ts >= ?) DESC, begin_ts DESC LIMIT ?""",
            (current-DAY,max_requests)).fetchall()
        for term,begin,end,attempts in pending:
            try:
                body=fetcher(term,begin,end)
                rows=validated_rows(body,term,begin,end)
                account_index.ingest_discovery(db_path,rows)
                accepted+=len(rows);requests+=1
                saturated=len(body.get("posts",[]))>=95 or (
                    isinstance(body.get("hitsTotal"),int) and body["hitsTotal"]>len(body["posts"])+5)
                if saturated and end-begin>MIN_WINDOW:
                    middle=begin+((end-begin)//2//HOUR)*HOUR
                    if begin<middle<end:
                        with db:
                            for lo,hi in ((begin,middle),(middle,end)):
                                db.execute("""INSERT OR IGNORE INTO public_index_windows
                                    (term,begin_ts,end_ts) VALUES(?,?,?)""",(term,lo,hi))
                            db.execute("""UPDATE public_index_windows SET status='split',accepted=?
                                WHERE term=? AND begin_ts=? AND end_ts=?""",(len(rows),term,begin,end))
                        split+=1
                        continue
                with db:
                    db.execute("""UPDATE public_index_windows SET status=?,accepted=?
                        WHERE term=? AND begin_ts=? AND end_ts=?""",
                        ("incomplete" if saturated else "done",len(rows),term,begin,end))
            except Exception as error:
                errors+=1;requests+=1
                with db:
                    db.execute("""UPDATE public_index_windows SET status=?,attempts=attempts+1,error=?
                        WHERE term=? AND begin_ts=? AND end_ts=?""",
                        ("failed" if attempts>=2 else "pending",
                         str(error)[:100] if str(error).startswith("public_search_unavailable:")
                         else type(error).__name__,term,begin,end))
        with db:
            db.execute("""INSERT INTO index_meta(key,value) VALUES('last_public_scan',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(str(now),))
        status=dict(db.execute("SELECT status,count(*) FROM public_index_windows GROUP BY status").fetchall())
        return {"requests":requests,"accepted":accepted,"errors":errors,"split":split,
                "windows":status,"scope":"public_bluesky_search_bounded"}
    finally:
        db.close()


def coverage(db_path):
    db=account_index.connect(db_path)
    try:
        _ensure_queue(db)
        return dict(db.execute("SELECT status,count(*) FROM public_index_windows GROUP BY status").fetchall())
    finally:db.close()
