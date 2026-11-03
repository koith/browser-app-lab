"""Public account metadata, public graph pages and thread snapshots for private TeraBox.

No private/follower-only access, no cross-site real-person resolution. Every
remote object is immutable and SHA read back before being called archived.
Provider rate limits, hidden lists and incomplete public threads are reported.
"""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, parse_qs
import json
import re
import time
from demand_archive import canonical_json, sha256, MIMES, MAX_MEDIA_BYTES
from target_account_archive import (
    SourceUnavailable, require_public_https, archive_key, cid_sha256,
    post_key, text_only, DID_RE
)

MAX_PROFILE_ASSET=24_000_000
MAX_GRAPH_PAGES_PER_RUN=2
MAX_THREAD_PER_RUN=6
MAX_THREAD_REPLIES=120
GRAPH_NAMES=("followers","following")
PROFILE_FILE_RE=re.compile(r"^snap-([0-9]{20})-([a-f0-9]{16})\.json$")
GRAPH_CHECK_RE=re.compile(r"^(followers|following)-([0-9]{8})\.json$")
THREAD_FILE_RE=re.compile(r"^snap-([0-9]{20})-([a-f0-9]{16})\.json$")
ALLOWED_ASSET_MIMES={"image/jpeg","image/png","image/webp","image/avif","image/gif"}


def timestamp_name(data:bytes)->str:
    return f"snap-{time.time_ns():020d}-{sha256(data)[:16]}.json"


def save_snapshot(cloud,prefix,obj):
    raw=canonical_json(obj)
    cloud.write_immutable(prefix+"/"+timestamp_name(raw),raw)


def safe_public_text(v,limit=4000):
    return v[:limit] if isinstance(v,str) else ""


def profile_metadata(profile,api):
    if profile["platform"]=="bluesky":
        raw=api.json("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?"+
                     urlencode({"actor":profile["identity"]}))
        if not isinstance(raw,dict) or raw.get("did")!=profile["identity"]:
            raise SourceUnavailable("public account profile identity mismatch")
        return {"identity":profile["identity"],"platform":"bluesky",
                "handle":safe_public_text(raw.get("handle"),200),
                "display_name":safe_public_text(raw.get("displayName"),300),
                "description":safe_public_text(raw.get("description"),10000),
                "avatar_url":raw.get("avatar"),"banner_url":raw.get("banner"),
                "followers_count":raw.get("followersCount"),
                "following_count":raw.get("followsCount"),
                "posts_count":raw.get("postsCount"),
                "indexed_at":raw.get("indexedAt"),
                "labels":raw.get("labels",[]),
                "raw":raw}
    raw=api.json(profile["pds"]+"/api/v1/accounts/"+profile["actor"])
    if not isinstance(raw,dict) or str(raw.get("id"))!=profile["actor"]:
        raise SourceUnavailable("public account profile identity mismatch")
    return {"identity":profile["identity"],"platform":"mastodon",
            "handle":safe_public_text(raw.get("acct"),200),
            "display_name":text_only(raw.get("display_name",""))[:300],
            "description":text_only(raw.get("note",""))[:10000],
            "avatar_url":raw.get("avatar_static") or raw.get("avatar"),
            "banner_url":raw.get("header_static") or raw.get("header"),
            "followers_count":raw.get("followers_count"),
            "following_count":raw.get("following_count"),
            "posts_count":raw.get("statuses_count"),
            "created_at":raw.get("created_at"),
            "fields":raw.get("fields",[]),
            "raw":raw}


def public_profile_images(profile,meta,api,archive):
    """Read original public PDS blob for Bluesky, public avatar/header for Mastodon."""
    images={}
    missing=[]
    record=None
    if profile["platform"]=="bluesky":
        try:
            record=api.json(profile["pds"]+"/xrpc/com.atproto.repo.getRecord?"+
                       urlencode({"repo":profile["identity"],
                                  "collection":"app.bsky.actor.profile","rkey":"self"}))
            if not isinstance(record,dict) or not isinstance(record.get("value"),dict):
                record=None
        except (RuntimeError,ValueError,TypeError):
            record=None
    for name,field in (("avatar","avatar"),("banner","banner")):
        url=meta.get(name+"_url")
        if not url:
            images[name]={"status":"not_set"}
            continue
        try:
            if profile["platform"]=="bluesky":
                blob=(record or {}).get("value",{}).get(field,{})
                ref=blob.get("ref") if isinstance(blob,dict) else None
                cid=ref.get("$link") if isinstance(ref,dict) else None
                mime=blob.get("mimeType") if isinstance(blob,dict) else None
                if not cid or mime not in ALLOWED_ASSET_MIMES:
                    raise SourceUnavailable("public profile original blob not exposed")
                source=profile["pds"]+"/xrpc/com.atproto.sync.getBlob?"+urlencode(
                    {"did":profile["identity"],"cid":cid})
                _got,data=api.media(source,mime)
                if sha256(data)!=cid_sha256(cid):
                    raise SourceUnavailable("profile original CID integrity mismatch")
            else:
                source=require_public_https(url)
                mime,data=api.media(source,None)
                if mime not in ALLOWED_ASSET_MIMES:
                    raise SourceUnavailable("unsupported public profile media type")
            if len(data)>MAX_PROFILE_ASSET or not data:
                raise SourceUnavailable("profile media size cap exceeded")
            key="profile/assets/"+sha256(data)+MIMES[mime]
            archive.write_immutable(key,data)
            images[name]={"status":"sha256_verified","key":key,"mime":mime,
                          "sha256":sha256(data),"bytes":len(data),
                          "source_url":source}
        except (RuntimeError,ValueError,TypeError):
            images[name]={"status":"unavailable"}
            missing.append(name)
    return images,missing


def archive_profile(profile,api,archive):
    meta=profile_metadata(profile,api)
    images,missing=public_profile_images(profile,meta,api,archive)
    # Preserve complete public provider response privately; viewer only exposes
    # the chosen profile's own public fields and image archive references.
    doc={**meta,"assets":images,"captured_at":datetime.now(timezone.utc).isoformat(),
         "complete_media":not missing}
    save_snapshot(archive,"profile/snapshots",doc)
    return {"profile_verified":True,"profile_assets_verified":
            sum(v.get("status")=="sha256_verified" for v in images.values()),
            "profile_assets_unavailable":len(missing)}


def social_graph_page(profile,kind,cursor,api):
    if kind not in GRAPH_NAMES:
        raise ValueError("invalid public graph direction")
    if profile["platform"]=="bluesky":
        route=("getFollowers" if kind=="followers" else "getFollows")
        q={"actor":profile["identity"],"limit":"100"}
        if cursor:q["cursor"]=cursor
        data=api.json("https://public.api.bsky.app/xrpc/app.bsky.graph."+route+"?"+
                      urlencode(q))
        if not isinstance(data,dict):
            raise SourceUnavailable("public follower graph unavailable")
        members=data.get("followers" if kind=="followers" else "follows")
        if not isinstance(members,list) or len(members)>100:
            raise SourceUnavailable("invalid public graph response")
        items=[]
        for m in members:
            if not isinstance(m,dict) or not isinstance(m.get("did"),str) or not DID_RE.fullmatch(m["did"]):
                continue
            items.append({"id":m["did"],"handle":safe_public_text(m.get("handle"),200),
                          "display_name":safe_public_text(m.get("displayName"),300),
                          "avatar_url":m.get("avatar"),
                          "profile_url":"https://bsky.app/profile/"+m["did"]})
        nxt=data.get("cursor")
        if nxt is not None and (not isinstance(nxt,str) or not 0<len(nxt)<=512):
            raise SourceUnavailable("invalid graph pagination cursor")
        return items,nxt,{"provider_count":len(members)}
    endpoint=profile["pds"]+"/api/v1/accounts/"+profile["actor"]+"/"+kind
    q={"limit":40}
    if cursor:
        if not str(cursor).isdigit():
            raise SourceUnavailable("invalid Mastodon graph cursor")
        q["max_id"]=cursor
    url=endpoint+"?"+urlencode(q)
    if hasattr(api,"json_with_headers"):
        raw,headers=api.json_with_headers(url)
    else:
        raw=api.json(url);headers={}
    if not isinstance(raw,list) or len(raw)>40:
        raise SourceUnavailable("invalid Mastodon graph response")
    items=[]
    for m in raw:
        if not isinstance(m,dict) or not isinstance(m.get("id"),str):
            continue
        link=m.get("url")
        try: require_public_https(link)
        except (ValueError,TypeError): continue
        items.append({"id":m["id"],"handle":safe_public_text(m.get("acct"),200),
                      "display_name":text_only(m.get("display_name",""))[:300],
                      "avatar_url":m.get("avatar_static") or m.get("avatar"),
                      "profile_url":link})
    # Mastodon follower edges have pagination IDs not represented in account IDs.
    # Never invent a cursor from the last returned account; only follow Link rel=next.
    nxt=None
    header=headers.get("Link",headers.get("link","")) if isinstance(headers,dict) else ""
    for element in header.split(","):
        match=re.search(r'<([^>]+)>\s*;\s*rel="?next"?',element)
        if match:
            link=require_public_https(match.group(1))
            parsed=urlsplit(link)
            if parsed.netloc!=urlsplit(endpoint).netloc or parsed.path!=urlsplit(endpoint).path:
                raise SourceUnavailable("unsafe graph pagination endpoint")
            candidates=parse_qs(parsed.query).get("max_id",[])
            if len(candidates)!=1 or not candidates[0].isdigit():
                raise SourceUnavailable("invalid graph next cursor")
            nxt=candidates[0]
            break
    return items,nxt,{"provider_count":len(raw),"next_link_observed":bool(nxt)}


def graph_checkpoint(cloud,kind):
    files=cloud.names("graph/checkpoints")
    selected=[(int(m.group(2)),n) for n in files
              if (m:=GRAPH_CHECK_RE.fullmatch(n)) and m.group(1)==kind]
    if not selected:
        return 0,None,False
    seq,name=max(selected)
    raw=cloud.read("graph/checkpoints/"+name,cap=4000)
    value=json.loads(raw)
    if (not isinstance(value,dict) or value.get("kind")!=kind
            or value.get("sequence")!=seq or not isinstance(value.get("exhausted"),bool)):
        raise SourceUnavailable("invalid archived graph checkpoint")
    cursor=value.get("next_cursor")
    if cursor is not None and not isinstance(cursor,str):
        raise SourceUnavailable("invalid archived graph checkpoint cursor")
    return seq,cursor,value["exhausted"]


def archive_graph(profile,kind,api,cloud,max_pages=1):
    max_pages=min(MAX_GRAPH_PAGES_PER_RUN,max(1,max_pages))
    seq,cursor,complete=graph_checkpoint(cloud,kind)
    if complete:
        # An already exhausted graph is not a claim that the account's
        # follower lists will remain unchanged in the future.
        cursor=None
        max_pages=1
    pages=members=0
    for _ in range(max_pages):
        users,nxt,info=social_graph_page(profile,kind,cursor,api)
        if nxt is not None and nxt==cursor:
            raise SourceUnavailable("public graph cursor did not progress")
        # Store public profile entries, not raw potentially private API fields.
        payload={"kind":kind,"items":users,"source_count":info["provider_count"],
                 "captured_at":datetime.now(timezone.utc).isoformat(),
                 "next_cursor":nxt}
        seq+=1
        cloud.write_immutable("graph/pages/"+kind+"-"+str(seq).zfill(8)+".json",
                              canonical_json(payload))
        cloud.write_immutable("graph/checkpoints/"+kind+"-"+str(seq).zfill(8)+".json",
                              canonical_json({"kind":kind,"sequence":seq,
                                              "next_cursor":nxt,"exhausted":nxt is None}))
        pages+=1
        members+=len(users)
        cursor=nxt
        if nxt is None:break
    return {"pages":pages,"members":members,"more_public_pages":cursor is not None}


def _thread_item_bluesky(item):
    if not isinstance(item,dict):
        return None
    post=item.get("post")
    if not isinstance(post,dict):
        return None
    uri=post.get("uri");author=post.get("author")
    if not isinstance(uri,str) or not isinstance(author,dict) or not isinstance(author.get("did"),str):
        return None
    value=post.get("record")
    if not isinstance(value,dict):
        return None
    return {"id":sha256(uri.encode())[:40],"uri":uri,
            "author":safe_public_text(author.get("handle"),200),
            "display_name":safe_public_text(author.get("displayName"),300),
            "text":safe_public_text(value.get("text"),30000),
            "posted_at":value.get("createdAt"),"media_urls":[],
            "raw_public":post}


def thread_page(profile,item,api):
    if profile["platform"]=="bluesky":
        data=api.json("https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread?"+
                      urlencode({"uri":item["original_id"],"depth":2,"parentHeight":1}))
        if not isinstance(data,dict) or not isinstance(data.get("thread"),dict):
            raise SourceUnavailable("public post thread unavailable")
        root=data["thread"]
        # Thread record returned for the selected source should match.
        root_post=root.get("post",{})
        if not isinstance(root_post,dict) or root_post.get("uri")!=item["original_id"]:
            raise SourceUnavailable("public post thread root mismatch")
        out=[]
        queue=list(root.get("replies") or [])
        while queue and len(out)<MAX_THREAD_REPLIES:
            reply=queue.pop(0)
            normalized=_thread_item_bluesky(reply)
            if normalized:out.append(normalized)
            if isinstance(reply,dict):
                queue.extend((reply.get("replies") or [])[:40])
        return {"replies":out,"truncated":bool(queue),
                "provider":"bluesky_public_thread"}
    sid=item["original_id"].rsplit(":",1)[-1]
    if not sid.isdigit():
        raise SourceUnavailable("invalid public Mastodon thread identifier")
    data=api.json(profile["pds"]+"/api/v1/statuses/"+sid+"/context")
    if not isinstance(data,dict) or not isinstance(data.get("descendants"),list):
        raise SourceUnavailable("public Mastodon reply context unavailable")
    out=[]
    rows=data["descendants"]
    for row in rows[:MAX_THREAD_REPLIES]:
        if not isinstance(row,dict) or row.get("visibility")!="public":
            continue
        account=row.get("account",{})
        if not isinstance(account,dict):continue
        out.append({"id":str(row.get("id","")),"uri":row.get("url") or row.get("uri"),
                    "author":safe_public_text(account.get("acct"),200),
                    "display_name":text_only(account.get("display_name",""))[:300],
                    "text":text_only(row.get("content","")),
                    "posted_at":row.get("created_at"),
                    "media_urls":[m.get("url") for m in (row.get("media_attachments") or [])
                                  if isinstance(m,dict) and m.get("url")],
                    "raw_public":row})
    return {"replies":out,"truncated":len(rows)>MAX_THREAD_REPLIES,
            "provider":"mastodon_public_context"}


def archive_thread(profile,item,api,cloud):
    thread=thread_page(profile,item,api)
    payload={"post_id":item["id"],"source_url":item["source_url"],
             "captured_at":datetime.now(timezone.utc).isoformat(),**thread}
    save_snapshot(cloud,"threads/"+item["id"],payload)
    return {"public_replies":len(thread["replies"]),
            "thread_truncated":thread["truncated"]}
