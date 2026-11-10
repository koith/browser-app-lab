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
import tempfile
import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from demand_archive import CloudArchive, canonical_json, post_key, sha256, MIMES, MAX_MEDIA_BYTES, MAX_CATALOG

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
        if raw.startswith("@"):
            raw = raw[1:]
        if raw.startswith("did:"):
            if not DID_RE.fullmatch(raw):
                raise ValueError("invalid Bluesky DID")
            return raw
        # A Bluesky short username is resolved under the official bsky.social
        # namespace. Custom-domain handles keep their existing full hostname.
        # The same canonical value is used in queue, workflow and manifest.
        if "." not in raw:
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{1,61}[A-Za-z0-9])", raw):
                raise ValueError("invalid Bluesky username")
            raw += ".bsky.social"
        if not allowed_host(raw) or any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                for part in raw.split(".")):
            raise ValueError("invalid Bluesky handle")
        return raw.lower()
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
    """Read legacy account files, store new originals in private flat TeraBox.

    The unofficial TeraBox backend may reject uploads under nested account
    directories (copyto missing). One-level root objects avoid that provider
    path resolution issue. Original logical keys, identity isolation and
    remote SHA256 checks remain unchanged.
    """

    def __init__(self, root, profile):
        self.account_hash=archive_key(profile)
        self.shared=CloudArchive(remote=root.remote,runner=root.runner)
        super().__init__(root.remote+"/account-archives/"+profile["platform"]+
                         "/"+self.account_hash,runner=root.runner)

    def shared_media_key(self,key):
        # Historical shallow media objects remain readable after this change.
        if not isinstance(key,str) or not re.fullmatch(
                r"posts/[a-f0-9]{40}/media/[0-9]{4}\.[a-z0-9]{2,10}",key):
            return None
        return "account-media-"+self.account_hash+"-"+sha256(key.encode("utf-8"))+".bin"

    def shared_record_key(self,key):
        """Reversible, namespaced root filename enables checkpoint discovery.

        A hash alone cannot support .names('graph/pages') or
        .names('metadata/checkpoints'), so encode the verified logical key.
        """
        if (not isinstance(key,str) or not 1<=len(key)<=135
                or not re.fullmatch(r"[A-Za-z0-9_./-]+",key)
                or key.startswith("/") or ".." in key or "//" in key):
            raise ValueError("invalid private account archive key")
        encoded=base64.urlsafe_b64encode(key.encode("ascii")).decode("ascii").rstrip("=")
        return "account-record-"+self.account_hash+"-"+encoded+".bin"

    def read(self,key,*,cap=MAX_CATALOG,optional=False,domain=None):
        # Always check prior canonical and account-local flat files FIRST.
        legacy=super().read(key,cap=cap,optional=True,domain=domain)
        if legacy is not None:
            return legacy
        historical=self.shared_media_key(key)
        if historical:
            raw=self.shared.read(historical,cap=cap,optional=True,domain=domain)
            if raw is not None:
                return raw
        shallow=self.shared_record_key(key)
        raw=self.shared.read(shallow,cap=cap,optional=True,domain=domain)
        if raw is not None:
            return raw
        if optional:
            return None
        raise RuntimeError("private account object unavailable")

    def names(self,prefix):
        legacy=super().names(prefix)
        # lsf is scoped to root level, not deeply nested directories.
        # Read only own account's flat namespace; never reveal other accounts.
        listing=self.shared.command(
            ["lsf",self.shared.remote+"/","--files-only",
             "--include","account-record-"+self.account_hash+"-*.bin",
             "--retries","2"],timeout=120,allow_missing=True)
        names=set(legacy)
        if listing:
            start="account-record-"+self.account_hash+"-"
            for filename in listing.decode("utf-8","replace").splitlines():
                if not filename.startswith(start) or not filename.endswith(".bin"):
                    continue
                encoded=filename[len(start):-4]
                try:
                    raw=base64.urlsafe_b64decode(encoded+"="*((-len(encoded))%4))
                    key=raw.decode("ascii")
                    if self.shared_record_key(key)!=filename:
                        continue
                except (ValueError,UnicodeDecodeError):
                    continue
                if key.startswith(prefix+"/"):
                    name=key[len(prefix)+1:]
                    if name and "/" not in name:
                        names.add(name)
        if len(names)>150000:
            raise ValueError("private account index exceeds safe bound")
        return sorted(names)

    def write_immutable(self,key,data):
        if not isinstance(data,bytes):
            raise TypeError("cloud content must be bytes")
        expected=sha256(data)
        cap=len(data)+1
        # Reject collisions in both historical domains; never overwrite
        # originals, even when a root-level replica is available.
        for domain in (None,"https://nephobox.com"):
            existing=super().read(key,cap=cap,optional=True,domain=domain)
            if existing is not None:
                if sha256(existing)!=expected:
                    raise RuntimeError("immutable account object checksum collision")
                return False
        historical=self.shared_media_key(key)
        if historical:
            for domain in (None,"https://nephobox.com"):
                old=self.shared.read(historical,cap=cap,optional=True,domain=domain)
                if old is not None:
                    if sha256(old)!=expected:
                        raise RuntimeError("immutable account media checksum collision")
                    return False
        # One depth-one immutable file for EVERY new logical account object:
        # source JSON, post/media, profile, graph, thread, entry, checkpoint.
        # No provider nested-folder mkdir/copyto requirement.
        shallow=self.shared_record_key(key)
        return self._write_flat_verified(shallow,data,expected,cap)

    def _write_flat_verified(self,shallow,data,expected,cap):
        """Only SHA-verified primary-domain writes; failover switches method.

        Live synthetic TeraBox probe #41981153740 verified primary copyto,
        copy, and rcat at root. Alternate-domain and nested uploads returned
        success WITHOUT remote SHA readback. Avoid both paths for new records.
        Never overwrite an existing different immutable object.
        """
        target=self.shared.remote+"/"+shallow
        for domain in (None,"https://nephobox.com"):
            try:
                seen=self.shared.read(shallow,cap=cap,optional=True,domain=domain)
            except ValueError as error:
                # A different oversized immutable object must block writes,
                # not trigger an unsafe overwrite or an unclassified failure.
                raise RuntimeError("immutable flat account checksum conflict") from error
            if seen is not None:
                if sha256(seen)!=expected:
                    raise RuntimeError("immutable flat account checksum conflict")
                return False
        errors=[]
        with tempfile.TemporaryDirectory(prefix="int-account-flat-") as folder:
            source=Path(folder)/shallow
            source.write_bytes(data)
            # Both methods were independently proven on real private TeraBox.
            # Switch method instead of retrying one broken provider path.
            commands=(
                ["copyto",str(source),target,"--ignore-existing",
                 "--timeout","15s","--retries","1"],
                ["copy",folder,self.shared.remote,"--ignore-existing",
                 "--timeout","15s","--retries","1"],
                ["copyto",str(source),target,"--ignore-existing",
                 "--timeout","15s","--retries","1"],
                ["copy",folder,self.shared.remote,"--ignore-existing",
                 "--timeout","15s","--retries","1"],
            )
            for attempt,args in enumerate(commands):
                if attempt:
                    time.sleep((0.5,1.5,3.0)[attempt-1])
                try:
                    self.shared.command(args,timeout=85)
                except RuntimeError as error:
                    # No raw stderr, paths, tokens or source records in logs.
                    errors.append(str(error).split(" (",1)[-1][:32])
                actual=self.shared.read_verified(shallow,expected,cap=cap)
                if actual==data:
                    return True
                if actual is not None:
                    raise RuntimeError("immutable flat account remote checksum conflict")
        # No false-green backup result when even the alternate proven method
        # could not read back the exact original bytes.
        raise RuntimeError("private account flat upload unverified after method fallback")


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
        # Public self-labels such as porn/sexual/nudity describe content,
        # not an access restriction. The original record retains its labels
        # for the private archive viewer to display. Dropping all such
        # records incorrectly makes a publicly accessible account look empty.
        # Never import provider-withheld, hidden or taken-down records.
        label_doc=value.get("labels")
        labels=label_doc.get("values",[]) if isinstance(label_doc,dict) else []
        if isinstance(labels,list) and any(
                isinstance(x,dict) and x.get("val") in ("!hide","!takedown")
                for x in labels):
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


# Revision records are always additional immutable objects. A provider edit
# NEVER rewrites the first verified post, its media, or its original source JSON.
REVISION_RE=re.compile(r"^[0-9]{8}T[0-9]{12}Z-[a-f0-9]{16}\.json$")


def visible_content_digest(item):
    """Fingerprint public authored content, excluding volatile social counts.

    Reply/repost counts are not edits to the author's own post. The provider's
    content payload, text, attachments and edit timestamp ARE versioned.
    """
    source=item["raw"]
    if item["platform"]=="bluesky":
        content=source.get("value")
        if not isinstance(content,dict):
            raise SourceUnavailable("invalid public source content")
    else:
        content={name:source.get(name) for name in (
            "content","spoiler_text","media_attachments","poll","card",
            "edited_at","language","sensitive","visibility","in_reply_to_id")}
    return sha256(canonical_json({
        "platform":item["platform"],"original_id":item["original_id"],
        "kind":item["kind"],"reply_to":item["reply_to"],"content":content}))


def latest_verified_content_digest(cloud,profile,item):
    """Read only immutable history; never infer edits from absent posts."""
    pid=item["id"]
    versions=[name for name in cloud.names("revisions/"+pid)
              if REVISION_RE.fullmatch(name)]
    if versions:
        last=max(versions)
        data=cloud.read("revisions/"+pid+"/"+last,cap=300_000)
        record=json.loads(data)
        digest=record.get("content_sha256")
        if (not isinstance(digest,str)
                or not re.fullmatch(r"[a-f0-9]{64}",digest)):
            raise SourceUnavailable("invalid immutable revision index")
        return digest
    first=cloud.read("metadata/source-records/"+pid+".json",
                     cap=MAX_SOURCE_BYTES,optional=True)
    if first is not None:
        try:
            baseline=normalize_record(profile,json.loads(first))
            if baseline is None:
                raise SourceUnavailable("invalid immutable first source")
            return visible_content_digest(baseline)
        except (TypeError,ValueError,KeyError):
            raise SourceUnavailable("invalid immutable first source") from None
    # Legacy backups without the first source record cannot prove a change.
    # Preserve their original bytes; never invent a historical revision.
    return None


def save_public_revision(cloud,profile,item,api):
    """Append a changed PUBLIC version plus independently checked media.

    The immutable first post, media, profile and source must not be touched.
    A disappearance, deletion or newly restricted post is not interpreted as
    an edit and therefore never destroys any previously stored version.
    """
    pid=item["id"]
    current=visible_content_digest(item)
    previous=latest_verified_content_digest(cloud,profile,item)
    if previous is None or current==previous:
        return False
    blobs=item["blobs"]
    if len(blobs)>MAX_MEDIA:
        raise SourceUnavailable("too many public revision attachments")
    captured=datetime.now(timezone.utc)
    stamp=captured.strftime("%Y%m%dT%H%M%S%fZ")
    version=stamp+"-"+current[:16]
    media=[]
    staged=[]
    for idx,(ref,mime) in enumerate(blobs,1):
        if profile["platform"]=="bluesky":
            if mime not in MIMES:
                raise SourceUnavailable("unsupported edited public media")
            url=(profile["pds"]+"/xrpc/com.atproto.sync.getBlob?"+
                 urlencode({"did":profile["identity"],"cid":ref}))
            expected=cid_sha256(ref)
            actual_mime,payload=api.media(url,mime)
            if sha256(payload)!=expected:
                raise SourceUnavailable("edited original PDS blob CID mismatch")
        else:
            url=ref
            actual_mime,payload=api.media(url,None)
        if (actual_mime not in MIMES or not isinstance(payload,bytes)
                or not 0<len(payload)<=MAX_MEDIA_BYTES):
            raise SourceUnavailable("edited original media unavailable")
        key=("revision-media/"+pid+"/"+version+"/"+
             str(idx).zfill(4)+MIMES[actual_mime])
        staged.append((key,payload))
        media.append({"key":key,"sha256":sha256(payload),
                      "bytes":len(payload),"mime":actual_mime,
                      "source_url":url,"remote_verified":True})
    # Store all media FIRST. The version index is committed only after every
    # payload's independent immutable remote readback has succeeded.
    for key,payload in staged:
        cloud.write_immutable(key,payload)
    revision={"schema_version":1,"post_id":pid,"source_url":item["source_url"],
              "original_id":item["original_id"],"platform":profile["platform"],
              "captured_at":captured.isoformat(),"content_sha256":current,
              "previous_content_sha256":previous,
              "text":item["text"],"kind":item["kind"],
              "reply_to":item["reply_to"],"source_record":item["raw"],
              "media":media,"media_expected":len(blobs),
              "media_saved":len(media),"archive_complete":True}
    cloud.write_immutable("revisions/"+pid+"/"+version+".json",
                          canonical_json(revision))
    return True


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
            clock=time.monotonic, archive_factory=None):
    cap=200 if os.getenv("DEMAND_TARGET_FULL_HISTORY","")=="1" else MAX_PAGES
    if not isinstance(max_pages,int) or not 1<=max_pages<=cap:
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
    archive=(archive_factory(root,profile) if archive_factory is not None
             else account_cloud(root,profile))
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
    saved=duplicates=restricted=media_pending=pages=revisions_added=0
    deadline=clock()+MAX_RUNTIME

    def capture_public_rows(records):
        nonlocal saved,duplicates,restricted,media_pending,revisions_added
        for raw in records:
            item=normalize_record(profile,raw)
            if not item:
                # Provider-restricted / hidden / removed records are NEVER
                # interpreted as deletions of previously saved originals.
                restricted+=1
                continue
            # Verify existing original from immutable SHA readback; a filename
            # alone cannot establish that a previous capture was complete.
            marker=archive.read("metadata/entries/"+item["id"]+".json",
                                cap=1024,optional=True)
            if marker is not None:
                try:
                    index=json.loads(marker)
                    posted=archive.read_verified(
                        "posts/"+item["id"]+"/post.json",index["sha256"],
                        cap=100_000)
                    if posted is not None:
                        if save_public_revision(archive,profile,item,api):
                            revisions_added+=1
                        else:
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

    try:
        # A partial historical cursor must not starve NEW posts and edits.
        # Always check the current first page before resuming older pages.
        if cursor and not previously_complete and clock()<deadline:
            fresh,_=page_records(profile,None,api)
            capture_public_rows(fresh)
        for _ in range(max_pages):
            if clock()>=deadline:
                break
            current_cursor=cursor
            records,next_cursor=page_records(profile,cursor,api)
            if records and next_cursor is not None and next_cursor==current_cursor:
                raise SourceUnavailable("public provider cursor did not advance")
            capture_public_rows(records)
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
                          "revisions_appended":revisions_added,
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
            "previously_saved":duplicates,"revisions_appended":revisions_added,
            "status":status,
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
