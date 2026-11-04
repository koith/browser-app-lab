"""Private, resumable, explicitly selected public-account history to TeraBox.

Only a profile's own currently public authored posts/replies are considered.
No private API, deleted-content recovery, password, scraping login, cross-account
identity matching or public GitHub artifacts. Every original PDS blob or public
Mastodon attachment must pass remote SHA readback before a page checkpoint.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import ipaddress
import json
import os
import re
import socket
from pathlib import Path
import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from demand_archive import CloudArchive, canonical_json, post_key, sha256, MIMES, MAX_MEDIA_BYTES

ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.:-]{3,260}$")
HOST_RE = re.compile(r"^[a-zA-Z0-9.-]{3,253}$")
DID_RE = re.compile(r"^did:plc:[a-z2-7]{24}$")
CID_RE = re.compile(r"^b[a-z2-7]{20,200}$")
CHECKPOINT_RE = re.compile(r"^page-([0-9]{8})\.json$")
REGISTRY_RE = re.compile(r"^(bluesky|mastodon)-([0-9a-f]{40})\.json$")
MAX_MEDIA = 16
MAX_RECORDS = 100
MAX_PAGES = 4
MAX_URL_BYTES = 2200
MAX_SOURCE_BYTES = 3_000_000
MAX_RUNTIME = 850


class SourceUnavailable(RuntimeError):
    pass


def allowed_host(host: str) -> bool:
    if not host or not HOST_RE.fullmatch(host) or host.lower() == "localhost":
        return False
    if host.endswith((".local", ".internal", ".localhost")) or ".." in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def require_public_https(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > MAX_URL_BYTES:
        raise ValueError("invalid public source URL")
    u = urlsplit(raw)
    if (u.scheme != "https" or not allowed_host(u.hostname or "") or u.username
            or u.password or u.port not in (None, 443) or u.fragment):
        raise ValueError("invalid public source URL")
    return raw


def require_global_dns(host: str) -> None:
    # Hostname-only checks do not prevent DNS rebinding to cloud metadata or
    # loopback endpoints. Refuse any non-global resolved IPv4/IPv6 address.
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses:
            raise ValueError("unresolvable public source")
        if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("nonpublic source address blocked")
    except OSError as error:
        raise SourceUnavailable("public source DNS unavailable") from error


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        require_public_https(newurl)
        require_global_dns(urlsplit(newurl).hostname)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class Transport:
    def __init__(self):
        self.opener = build_opener(SafeRedirect())

    def read(self, url, *, cap=MAX_SOURCE_BYTES, body=None):
        require_public_https(url)
        require_global_dns(urlsplit(url).hostname)
        payload = canonical_json(body) if body is not None else None
        req = Request(url, data=payload, headers={
            "Accept": "application/json, image/*, video/*, audio/*, application/octet-stream",
            "User-Agent": "INTERSECTION-PublicAccountArchive/1.0",
            **({"Content-Type": "application/json"} if body is not None else {})
        })
        try:
            with self.opener.open(req, timeout=20) as response:
                raw = response.read(cap+1)
                mime = response.headers.get("Content-Type", "").split(";")[0].lower()
            if not 0 < len(raw) <= cap:
                raise SourceUnavailable("source response exceeds configured byte bound")
            return mime, raw
        except (OSError, TimeoutError) as error:
            raise SourceUnavailable("public source unavailable") from error

    def json_with_headers(self,url):
        """Return public JSON and Link header for genuine Mastodon pagination."""
        require_public_https(url)
        require_global_dns(urlsplit(url).hostname)
        req=Request(url,headers={"Accept":"application/json",
                                 "User-Agent":"INTERSECTION-PublicAccountArchive/1.0"})
        try:
            with self.opener.open(req,timeout=20) as response:
                raw=response.read(MAX_SOURCE_BYTES+1)
                headers={"Link":response.headers.get("Link","")}
            if not 0<len(raw)<=MAX_SOURCE_BYTES:
                raise SourceUnavailable("public source response bound exceeded")
            return json.loads(raw),headers
        except (OSError,TimeoutError,ValueError) as error:
            raise SourceUnavailable("public source pagination unavailable") from error

    def json(self, url, body=None):
        _mime, raw = self.read(url, body=body)
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError) as error:
            raise SourceUnavailable("invalid public source response") from error

    def media(self, url, mime):
        actual, blob = self.read(url, cap=MAX_MEDIA_BYTES)
        # Authoritative ATProto blob record MIME is used when PDS responds
        # with application/octet-stream; otherwise require a matching class.
        if (mime is not None and actual and actual != "application/octet-stream"
                and actual != mime):
            raise SourceUnavailable("source media MIME mismatch")
        return (mime or actual), blob


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data = []
    def handle_data(self, value):
        self.data.append(value)


def text_only(markup):
    if not isinstance(markup, str):
        return ""
    parser = TextOnly()
    parser.feed(markup[:60000])
    return "".join(parser.data)[:30000]


def profile_input(platform, raw):
    if platform not in ("bluesky", "mastodon") or not isinstance(raw, str):
        raise ValueError("unsupported public account source")
    raw = raw.strip()
    if not 3 <= len(raw) <= 260:
        raise ValueError("invalid account input")
    if platform == "bluesky":
        if raw.startswith("https://"):
            url = urlsplit(require_public_https(raw))
            if url.hostname != "bsky.app" or not url.path.startswith("/profile/"):
                raise ValueError("invalid Bluesky profile URL")
            raw = url.path[len("/profile/"):].strip("/")
        raw = raw.lstrip("@")
        if not ACCOUNT_RE.fullmatch(raw) or "/" in raw:
            raise ValueError("invalid Bluesky profile")
        if raw.startswith("did:") and not DID_RE.fullmatch(raw):
            raise ValueError("invalid Bluesky DID")
        return raw
    if raw.startswith("https://"):
        u = urlsplit(require_public_https(raw))
        if not re.fullmatch(r"/@[A-Za-z0-9_][A-Za-z0-9_.-]{0,59}/?",u.path):
            raise ValueError("invalid Mastodon profile URL")
        return u.hostname.lower(), u.path.strip("/").lstrip("@")
    if raw.startswith("@"):
        raw = raw[1:]
    parts = raw.split("@")
    if (len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,59}",parts[0])
            or not allowed_host(parts[1])):
        raise ValueError("Mastodon account needs user@instance")
    return parts[1].lower(), parts[0]


def resolve(platform, raw, api):
    value = profile_input(platform, raw)
    if platform == "bluesky":
        actor = value
        profile = api.json("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?" +
                           urlencode({"actor":actor}))
        did = profile.get("did") if isinstance(profile,dict) else None
        handle = profile.get("handle") if isinstance(profile,dict) else None
        if not isinstance(did,str) or not DID_RE.fullmatch(did) or not isinstance(handle,str):
            raise SourceUnavailable("verified public Bluesky DID unavailable")
        doc = api.json("https://plc.directory/"+quote(did,safe=":"))
        services = doc.get("service",[]) if isinstance(doc,dict) else []
        endpoints = [s.get("serviceEndpoint") for s in services if isinstance(s,dict)
                     and s.get("id") in ("#atproto_pds",did+"#atproto_pds")]
        if len(endpoints)!=1 or not isinstance(endpoints[0],str):
            raise SourceUnavailable("Bluesky PDS endpoint unavailable")
        endpoint = require_public_https(endpoints[0].rstrip("/"))
        if urlsplit(endpoint).path not in ("","/") or urlsplit(endpoint).query:
            raise SourceUnavailable("unsafe Bluesky PDS endpoint")
        return {"platform":platform,"identity":did,"actor":did,
                "profile_url":"https://bsky.app/profile/"+quote(did,safe=":"),
                "pds":endpoint}
    host,user=value
    endpoint="https://"+host
    account=api.json(endpoint+"/api/v1/accounts/lookup?"+urlencode({"acct":user}))
    if (not isinstance(account,dict) or not str(account.get("id","")).isdigit()
            or not isinstance(account.get("url"),str)):
        raise SourceUnavailable("verified public Mastodon account unavailable")
    return {"platform":platform,"identity":host+":"+str(account["id"]),
            "actor":str(account["id"]),"profile_url":account["url"],
            "pds":endpoint}


def archive_key(profile):
    return sha256((profile["platform"]+"\0"+profile["identity"]).encode())[:40]


class AccountCloudArchive(CloudArchive):
    """Private account store with a depth-one immutable original-media fallback.

    TeraBox's unofficial backend intermittently returns missing for nested
    copyto paths even after mkdir/lsf succeeds. All existing canonical and
    account-local flat files retain priority; only verified media bytes use
    a deterministic root-level SHA-addressed object on fresh writes.
    """

    def __init__(self, root, profile):
        self.account_hash=archive_key(profile)
        self.shared=CloudArchive(remote=root.remote,runner=root.runner)
        super().__init__(root.remote+"/account-archives/"+profile["platform"]+
                         "/"+self.account_hash,runner=root.runner)

    def shared_media_key(self,key):
        if not isinstance(key,str) or not re.fullmatch(
                r"posts/[a-f0-9]{40}/media/[0-9]{4}\\.[a-z0-9]{2,10}",key):
            return None
        return "account-media-"+self.account_hash+"-"+sha256(key.encode("utf-8"))+".bin"

    def read(self,key,*,cap=3_000_000,optional=False,domain=None):
        # Original canonical and legacy account-local flat paths are preferred.
        original=super().read(key,cap=cap,optional=True,domain=domain)
        if original is not None:
            return original
        shallow=self.shared_media_key(key)
        if shallow:
            raw=self.shared.read(shallow,cap=cap,optional=True,domain=domain)
            if raw is not None:
                return raw
        if optional:
            return None
        return super().read(key,cap=cap,optional=False,domain=domain)

    def write_immutable(self,key,data):
        shallow=self.shared_media_key(key)
        if shallow is None:
            return super().write_immutable(key,data)
        if not isinstance(data,bytes):
            raise TypeError("cloud content must be bytes")
        expected=sha256(data)
        cap=len(data)+1
        # Never mask conflicting canonical or legacy immutable objects.
        for domain in (None,"https://nephobox.com"):
            existing=super().read(key,cap=cap,optional=True,domain=domain)
            if existing is None:
                continue
            if sha256(existing)!=expected:
                raise RuntimeError("immutable account media checksum collision")
            return False
        # One shallow file in the same private TeraBox root, unique to the
        # verified account AND original source slot. No additional folder
        # creation, unsafe overwrite, public media or external storage.
        written=self.shared.write_immutable(shallow,data)
        actual=self.shared.read_verified(shallow,expected,cap=cap)
        if actual!=data:
            raise RuntimeError("private account media shallow SHA readback failed")
        return written


def account_cloud(root, profile):
    return AccountCloudArchive(root,profile)


def cid_sha256(cid):
    """Extract CIDv1 raw sha2-256 digest for original ATProto blob checks."""
    if not isinstance(cid,str) or not CID_RE.fullmatch(cid):
        raise ValueError("invalid ATProto blob CID")
    text=cid[1:].upper()
    binary=base64.b32decode(text+"="*((-len(text))%8))
    def varint(pos):
        out=shift=0
        for _ in range(10):
            byte=binary[pos]
            pos+=1
            out|=(byte&127)<<shift
            if not byte&128:
                return out,pos
            shift+=7
        raise ValueError("invalid blob multihash")
    try:
        version,pos=varint(0)
        codec,pos=varint(pos)
        algorithm,pos=varint(pos)
        size,pos=varint(pos)
        if version!=1 or codec!=0x55 or algorithm!=0x12 or size!=32 or len(binary)-pos!=32:
            raise ValueError("unsupported blob CID digest")
        return binary[pos:].hex()
    except (IndexError,ValueError) as error:
        raise ValueError("unsupported blob CID digest") from error


def atproto_blobs(record):
    """Original ATProto image/video/audio blob refs, not transformed CDN thumbs."""
    found=[]
    def walk(value):
        if isinstance(value,dict):
            ref=value.get("ref")
            cid=ref.get("$link") if isinstance(ref,dict) else None
            mime=value.get("mimeType")
            if (value.get("$type")=="blob" and isinstance(cid,str)
                    and isinstance(mime,str) and mime in MIMES):
                found.append((cid,mime))
                return
            for item in value.values():
                walk(item)
        elif isinstance(value,list):
            for item in value:
                walk(item)
    walk(record.get("embed",{}))
    # One content-addressed CID can appear in multiple metadata positions.
    return list(dict.fromkeys(found))


def page_records(profile, cursor, api):
    if profile["platform"]=="bluesky":
        params={"repo":profile["actor"],"collection":"app.bsky.feed.post","limit":100}
        if cursor:
            params["cursor"]=cursor
        data=api.json(profile["pds"]+"/xrpc/com.atproto.repo.listRecords?"+urlencode(params))
        if not isinstance(data,dict) or not isinstance(data.get("records"),list):
            raise SourceUnavailable("invalid public repo listing")
        rows=data["records"]
        if len(rows)>100:
            raise SourceUnavailable("unbounded public repo listing")
        next_cursor=data.get("cursor")
        if next_cursor is not None and (not isinstance(next_cursor,str)
                                        or not 0<len(next_cursor)<=512):
            raise SourceUnavailable("invalid public record cursor")
        return rows,next_cursor
    params={"limit":40,"exclude_reblogs":"true","exclude_replies":"false"}
    if cursor:
        if not str(cursor).isdigit():
            raise ValueError("unsafe Mastodon cursor")
        params["max_id"]=cursor
    rows=api.json(profile["pds"]+"/api/v1/accounts/"+profile["actor"]+
                  "/statuses?"+urlencode(params))
    if not isinstance(rows,list) or len(rows)>40:
        raise SourceUnavailable("invalid public status listing")
    next_cursor=str(rows[-1].get("id","")) if rows else None
    if next_cursor is not None and not next_cursor.isdigit():
        raise SourceUnavailable("invalid public status cursor")
    return rows,next_cursor


def normalize_record(profile, raw):
    """Require the exact resolved author and public source, including replies."""
    if not isinstance(raw,dict):
        return None
    platform=profile["platform"]
    if platform=="bluesky":
        uri=raw.get("uri")
        value=raw.get("value")
        if (not isinstance(uri,str) or not isinstance(value,dict)
                or not uri.startswith("at://"+profile["identity"]+"/app.bsky.feed.post/")):
            return None
        if value.get("$type") not in (None,"app.bsky.feed.post"):
            return None
        if value.get("labels",{}).get("values") if isinstance(value.get("labels"),dict) else False:
            labels=value["labels"]["values"]
            if any(isinstance(x,dict) and x.get("val") in
                   ("!hide","!takedown","porn","sexual","nudity") for x in labels):
                return None
        rkey=uri.rsplit("/",1)[-1]
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,100}",rkey):
            return None
        return {"id":post_key(platform,uri),"original_id":uri,
                "source_url":profile["profile_url"]+"/post/"+rkey,
                "posted_at":value.get("createdAt"),"text":str(value.get("text",""))[:30000],
                "kind":"reply" if value.get("reply") else "post",
                "reply_to":(value.get("reply",{}).get("parent",{}).get("uri","")
                            if isinstance(value.get("reply"),dict) else ""),
                "blobs":atproto_blobs(value),"raw":raw}
    if not isinstance(raw.get("account"),dict) or str(raw["account"].get("id")) != profile["actor"]:
        return None
    if raw.get("visibility")!="public" or raw.get("sensitive") or raw.get("reblog"):
        return None
    sid=str(raw.get("id",""))
    if not sid.isdigit():
        return None
    uri=raw.get("url") or raw.get("uri")
    if not isinstance(uri,str):
        return None
    try:
        require_public_https(uri)
    except ValueError:
        return None
    attachments=raw.get("media_attachments") or []
    refs=[]
    if not isinstance(attachments,list):
        return None
    for item in attachments:
        if not isinstance(item,dict):
            continue
        src=item.get("url")
        if isinstance(src,str) and item.get("type") in ("image","video","gifv","audio"):
            try:
                require_public_https(src)
            except ValueError:
                continue
            refs.append((src,None))
    return {"id":post_key(platform,profile["identity"]+":"+sid),
            "original_id":profile["identity"]+":"+sid,
            "source_url":uri,"posted_at":raw.get("created_at"),
            "text":text_only(raw.get("content","")),
            "kind":"reply" if raw.get("in_reply_to_id") else "post",
            "reply_to":str(raw.get("in_reply_to_id") or ""),
            "blobs":refs,"raw":raw}


def save_public_record(cloud, profile, item, api):
    pid=item["id"]
    blobs=item["blobs"]
    if len(blobs)>MAX_MEDIA:
        raise SourceUnavailable("too many original media attachments")
    try:
        posted=datetime.fromisoformat(str(item["posted_at"]).replace("Z","+00:00"))
        if posted.tzinfo is None or posted>datetime.now(timezone.utc):
            raise ValueError("out of range timestamp")
    except (TypeError,ValueError) as error:
        raise SourceUnavailable("invalid original public timestamp") from error

    # Save complete source JSON privately; exact original reply-parent,
    # facets, labels, alt text and external cards remain available.
    cloud.write_immutable("metadata/source-records/"+pid+".json",
                          canonical_json(item["raw"]))
    media=[]
    payloads=[]
    for index,(ref,mime) in enumerate(blobs,1):
        source_url=ref
        try:
            if profile["platform"]=="bluesky":
                assert mime in MIMES
                source_url=(profile["pds"]+"/xrpc/com.atproto.sync.getBlob?"+
                            urlencode({"did":profile["identity"],"cid":ref}))
                expected=cid_sha256(ref)
                _,data=api.media(source_url,mime)
                if sha256(data)!=expected:
                    raise SourceUnavailable("original PDS CID mismatch")
                current_mime=mime
            else:
                current_mime,data=api.media(source_url,None)
                if current_mime not in MIMES:
                    raise SourceUnavailable("unsupported original media format")
            if not 0<len(data)<=MAX_MEDIA_BYTES:
                raise SourceUnavailable("missing or oversized original attachment")
        except (RuntimeError,ValueError,AssertionError):
            # Only exact matching immutable staged media is eligible for reuse.
            existing=cloud.read_staged_media(pid,index,expected_source_url=source_url)
            if existing is None:
                continue
            current_mime,data=existing
        media.append({"key":"posts/"+pid+"/media/"+str(index).zfill(4)+MIMES[current_mime],
                      "mime":current_mime,"bytes":len(data),"sha256":sha256(data),
                      "remote_verified":True,"source_url":source_url,
                      "kind":"audio" if current_mime.startswith("audio/") else
                             "video" if current_mime.startswith("video/") else "image"})
        payloads.append(data)
    post={"id":pid,"platform":profile["platform"],"source_url":item["source_url"],
          "posted_at":posted.isoformat(),"captured_at":datetime.now(timezone.utc).isoformat(),
          "text":item["text"],"profile_url":profile["profile_url"],
          "kind":item["kind"],"reply_to":item["reply_to"],"original_id":item["original_id"],
          "media":media,"media_expected":len(blobs),"media_saved":len(media),
          "archive_complete":len(blobs)==len(media),
          "provenance":"selected_public_account","retention_review":"required_on_removal_request"}
    if not post["archive_complete"]:
        if media:
            cloud.stage_partial_media(post,payloads)
        raise SourceUnavailable("original media incomplete; cursor not advanced")
    cloud.save_post(post,payloads)
    return post


def state_from_cloud(cloud):
    names=[(int(m.group(1)),n) for n in cloud.names("metadata/checkpoints")
           if (m:=CHECKPOINT_RE.fullmatch(n))]
    if not names:
        return 0,None,False
    seq,name=max(names)
    state=json.loads(cloud.read("metadata/checkpoints/"+name,cap=5000))
    if (not isinstance(state,dict) or state.get("sequence")!=seq
            or not isinstance(state.get("source_exhausted"),bool)):
        raise SourceUnavailable("unverified account-history checkpoint")
    cursor=state.get("next_cursor")
    if cursor is not None and (not isinstance(cursor,str) or len(cursor)>512):
        raise SourceUnavailable("unverified account-history cursor")
    return seq,cursor,state["source_exhausted"]


def run_one(platform, raw_account, *, root=None, api=None, max_pages=2,
            clock=time.monotonic):
    if not isinstance(max_pages,int) or not 1<=max_pages<=MAX_PAGES:
        raise ValueError("invalid per-run page budget")
    api=api or Transport()
    root=root or CloudArchive()
    root.preflight()
    profile=resolve(platform,raw_account,api)
    identity=archive_key(profile)
    registration={"schema_version":1,"platform":platform,
                  "identity":profile["identity"],"actor":profile["actor"],
                  "profile_url":profile["profile_url"],"pds":profile["pds"]}
    root.write_immutable("metadata/target-accounts/"+platform+"-"+identity+".json",
                         canonical_json(registration))
    archive=account_cloud(root,profile)
    seq,cursor,previously_complete=state_from_cloud(archive)
    # Profile and public social-graph snapshots are independent from post
    # history checkpoints. An API restriction is counted, never bypassed.
    from target_account_enrichment import archive_profile, archive_graph, backfill_public_threads
    profile_stat={"profile_verified":False,"profile_assets_verified":0,
                  "profile_assets_unavailable":0}
    graph_stats={}
    try:
        profile_stat=archive_profile(profile,api,archive)
    except (RuntimeError,ValueError,TypeError,KeyError):
        pass
    for graph_kind in ("followers","following"):
        try:
            graph_stats[graph_kind]=archive_graph(profile,graph_kind,api,archive)
        except (RuntimeError,ValueError,TypeError,KeyError):
            graph_stats[graph_kind]={"pages":0,"members":0,"more_public_pages":None}
    if previously_complete:
        # Re-check newest public posts after historical backfill completed.
        cursor=None
        max_pages=min(max_pages,1)
    saved=duplicates=restricted=media_pending=pages=0
    deadline=clock()+MAX_RUNTIME
    try:
        for _ in range(max_pages):
            if clock()>=deadline:
                break
            current_cursor=cursor
            records,next_cursor=page_records(profile,cursor,api)
            if records and next_cursor is not None and next_cursor==current_cursor:
                raise SourceUnavailable("public provider cursor did not advance")
            for raw in records:
                item=normalize_record(profile,raw)
                if not item:
                    restricted+=1
                    continue
                # Existing original is read back, not deduplicated from an
                # untrusted/possibly stale filename listing alone.
                marker=archive.read("metadata/entries/"+item["id"]+".json",
                                    cap=1024,optional=True)
                if marker is not None:
                    try:
                        index=json.loads(marker)
                        posted=archive.read_verified(
                            "posts/"+item["id"]+"/post.json",index["sha256"],
                            cap=100_000)
                        if posted is not None:
                            duplicates+=1
                            continue
                    except (ValueError,KeyError,TypeError):
                        pass
                try:
                    save_public_record(archive,profile,item,api)
                    saved+=1
                except SourceUnavailable:
                    media_pending+=1
                    raise
            seq+=1
            exhausted=not records or not next_cursor
            archive.write_immutable("metadata/checkpoints/page-"+str(seq).zfill(8)+".json",
                                    canonical_json({"sequence":seq,
                                       "next_cursor":None if exhausted else next_cursor,
                                       "source_exhausted":exhausted,
                                       "record_count":len(records),
                                       "recorded_at":datetime.now(timezone.utc).isoformat()}))
            pages+=1
            cursor=next_cursor
            if exhausted:
                break
        status="COMPLETE_CURRENT_PUBLIC_CURSOR" if pages and not cursor else "RESUME_NEEDED"
        # Bounded comment/thread backlog scans retain progress even when
        # the selected source has thousands of historical posts.
        try:
            thread_stats=backfill_public_threads(profile,api,archive)
        except (RuntimeError,ValueError,TypeError,KeyError):
            thread_stats={"threads_verified":0,"threads_pending":True}
    except (RuntimeError,ValueError):
        status="FAILED_RETRYABLE"
        raise
    finally:
        # Never print account/profile URL, post IDs, text, raw API errors or media.
        print("TARGET_ACCOUNT_ARCHIVE_AGGREGATE",
              json.dumps({"platform":platform,"pages_verified":pages,
                          "posts_verified":saved,"previously_saved":duplicates,
                          "excluded_not_public":restricted,
                          "media_pending":media_pending,
                          "profile_verified":profile_stat["profile_verified"],
                          "profile_assets_verified":profile_stat["profile_assets_verified"],
                          "profile_assets_unavailable":profile_stat["profile_assets_unavailable"],
                          "graph_pages_verified":sum(v["pages"] for v in graph_stats.values()),
                          "graph_pages_pending":sum(v.get("more_public_pages") is not False for v in graph_stats.values()),
                          "threads_verified":locals().get("thread_stats",{}).get("threads_verified",0),
                          "threads_pending":locals().get("thread_stats",{}).get("threads_pending",True),
                          "state":locals().get("status","FAILED_RETRYABLE")},
                         sort_keys=True),flush=True)
    return {"platform":platform,"pages_verified":pages,"posts_verified":saved,
            "previously_saved":duplicates,"status":status,
            "profile":profile_stat,"graph":graph_stats,
            "threads":locals().get("thread_stats",{})}


def read_bootstrap_request(path=None):
    """Load only a reviewed public profile, with no credential or media in Git."""
    source=Path(path) if path is not None else Path(__file__).with_name("target_account_bootstrap.json")
    if not source.is_file():
        return None
    data=json.loads(source.read_text(encoding="utf-8"))
    if (type(data) is not dict or set(data)!={"schema_version","platform","account","max_pages"}
            or data.get("schema_version")!=1 or type(data.get("max_pages")) is not int
            or not 1<=data["max_pages"]<=MAX_PAGES):
        raise ValueError("invalid reviewed target request")
    profile_input(data["platform"],data["account"])
    return data


def run_registered(*, root=None, api=None, max_accounts=2, bootstrap=False,
                   bootstrap_path=None):
    root=root or CloudArchive()
    root.preflight()
    names=sorted(n for n in root.names("metadata/target-accounts")
                 if REGISTRY_RE.fullmatch(n))
    if not names:
        # On initial TeraBox registration failure, retry the reviewed profile
        # on the next schedule instead of repeatedly reporting an empty run.
        request=read_bootstrap_request(bootstrap_path) if bootstrap else None
        if request is not None:
            result=run_one(request["platform"],request["account"],root=root,api=api,
                           max_pages=request["max_pages"])
            print("TARGET_ACCOUNT_ARCHIVE_SCHEDULE",
                  json.dumps({"registered":1,"processed":1,"initial_registration":True,
                              "posts_verified":result["posts_verified"],
                              "state":result["status"]},sort_keys=True),flush=True)
            return
        print("TARGET_ACCOUNT_ARCHIVE_SCHEDULE",
              json.dumps({"registered":0,"processed":0,
                          "state":"NO_REGISTERED_TARGETS"},sort_keys=True),flush=True)
        raise RuntimeError("no registered public accounts; no account backup performed")
    # Rotate the bounded slot each UTC cycle to avoid starving older entries.
    slot=int(time.time()//21600)%len(names)
    selected=[names[(slot+i)%len(names)] for i in range(min(max_accounts,len(names)))]
    failures=0
    for name in selected:
        try:
            item=json.loads(root.read("metadata/target-accounts/"+name,cap=3000))
            platform=item["platform"]
            if platform=="bluesky":
                account=item["identity"]
            else:
                account=item["profile_url"]
            run_one(platform,account,root=root,api=api)
        except (RuntimeError,ValueError,KeyError,TypeError):
            failures+=1
    print("TARGET_ACCOUNT_ARCHIVE_SCHEDULE",
          json.dumps({"registered":len(names),"processed":len(selected),
                      "failed":failures},sort_keys=True),flush=True)
    if failures:
        raise RuntimeError("some registered public archives remain unverified")


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--platform",choices=["bluesky","mastodon"])
    cli.add_argument("--account")
    cli.add_argument("--resume-registered",action="store_true")
    cli.add_argument("--max-pages",type=int,default=2)
    args=cli.parse_args()
    if args.resume_registered:
        if args.platform or args.account:
            cli.error("scheduled resume does not accept a manually targeted account")
        run_registered(bootstrap=True)
    elif args.platform and args.account:
        run_one(args.platform,args.account,max_pages=args.max_pages)
    else:
        cli.error("select platform and account, or resume registered public archives")
