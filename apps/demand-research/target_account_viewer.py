"""Authenticated read-only SNS-like viewer of verified private account archives.

Endpoints never fetch provider posts. They expose only previously stored private
TeraBox records to the owner of the private gateway's signed HttpOnly session.
No repo logs/analytics, broad CORS, unverified media or account identifier leaks.
"""
from __future__ import annotations

import gc
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse, FileResponse, Response
from demand_archive import CloudArchive, sha256
import github_temp_bundle
from target_account_archive import REGISTRY_RE, archive_key, account_cloud, text_only
from target_account_enrichment import PROFILE_FILE_RE, THREAD_FILE_RE
from verified_bundle_reader import (
    VerifiedBundle, BundleAccountCloud, MergedBundleAccountCloud, available_bundles, latest_account_bundle, BundleInvalid,
)

HEX40=re.compile(r"^[a-f0-9]{40}$")
GRAPH_PAGE=re.compile(r"^(followers|following)-([0-9]{8})\.json$")
VIEW_DIR=Path(__file__).resolve().parent
CACHE_HEADERS={"Cache-Control":"private, no-store",
               "X-Content-Type-Options":"nosniff",
               "Referrer-Policy":"no-referrer",
               "X-Robots-Tag":"noindex, nofollow"}


def open_root():
    return CloudArchive()


class _BoundedZipRoot:
    """Keep unreliable private-cloud reads from stalling the GitHub fallback.

    This wrapper is only for immutable ZIP discovery. Legacy per-record paths
    continue using the original CloudArchive and its own timeout policy.
    """
    def __init__(self,root):
        self.root=root
        self.remote=root.remote
        self.authorization_denied=False

    def command(self,args,*,data=None,timeout=150,allow_missing=False):
        operation=args[0] if args and args[0] in ("lsf","cat") else "other"
        # When a provider denies one immutable ZIP, do not issue another
        # eight known-denied requests in the same collection pass.
        if self.authorization_denied and operation=="cat":
            raise RuntimeError("Private ZIP read unavailable (authorization)")
        # The exact 17.6 MB original ZIP was independently SHA verified on
        # GitHub Actions. An 18-second per-operation listing/read budget dropped
        # this same ZIP on the slower Render free instance. Keep a finite
        # per-operation bound and let GitHub remain a separate safe fallback.
        budget=min(timeout,55 if operation=="cat" else 30)
        started=time.monotonic()
        outcome="error"
        try:
            response=self.root.command(args,data=data,timeout=budget,
                                       allow_missing=allow_missing)
            outcome="missing" if response is None else "ok"
            return response
        except RuntimeError as error:
            if isinstance(error.__cause__,subprocess.TimeoutExpired):
                outcome="process_timeout"
            else:
                for category in ("authorization","missing","rate_limited",
                                 "network_timeout","capacity","remote_server",
                                 "backend_rejected"):
                    if "("+category+")" in str(error):
                        outcome=category
                        if category=="authorization":
                            self.authorization_denied=True
                        break
            raise
        finally:
            # Fixed categories and durations ONLY; never log original account
            # IDs, post text, private path, ZIP bytes, cookie, or provider body.
            print("INTERSECTION_ZIP_SOURCE_READ",
                  "operation="+operation,
                  "outcome="+outcome,
                  "elapsed_ms="+str(round((time.monotonic()-started)*1000)),
                  flush=True)


_ZIP_SESSION_CACHE=None
_ZIP_SESSION_LOCK=threading.Lock()
ZIP_VERIFIED_SESSION_SECONDS=90
# A known-denied ZIP source must not block every verified GitHub media read.
ZIP_UNAVAILABLE_BACKOFF_SECONDS=150


def _verified_account_bundles(root):
    """Reuse independently SHA-verified TeraBox ZIPs; singleflight 403 probes.

    On Render's 512 MiB free instance, an unavailable TeraBox ZIP used to
    trigger one rclone listing + denied cat for every parallel feed, profile,
    graph, thread and media request. The old cache protected only AFTER the
    remote call returned; concurrent requests all bypassed it. Serialize
    that one bounded remote probe and share its verified result or safely
    classified temporary failure across the whole browsing session.
    Synthetic roots continue using the original independent reader.
    """
    global _ZIP_SESSION_CACHE
    if not github_temp_bundle.enabled():
        return available_bundles(root)
    cacheable=type(root) is CloudArchive
    if not cacheable:
        return tuple(available_bundles(_BoundedZipRoot(root)))
    # LOCK BEFORE checking the cache and KEEP it during the remote probe.
    # This deliberately trades duplicate blocking worker threads for one
    # provider request without extending network permissions or bypassing
    # SHA256. The subprocess retains its strict operation timeout.
    with _ZIP_SESSION_LOCK:
        now=time.monotonic()
        cached=_ZIP_SESSION_CACHE
        if cached is not None and cached[0]==root.remote:
            ttl=(ZIP_UNAVAILABLE_BACKOFF_SECONDS if cached[3]
                 else ZIP_VERIFIED_SESSION_SECONDS)
            if now-cached[1]<ttl:
                if cached[3]:
                    raise RuntimeError("Private ZIP provider temporarily unavailable")
                return cached[2]
        try:
            # Materialize while the per-pass authorization circuit breaker
            # is alive, not after its wrapper has been discarded.
            result=tuple(available_bundles(_BoundedZipRoot(root)))
        except (RuntimeError,ValueError,TypeError,BundleInvalid):
            _ZIP_SESSION_CACHE=(root.remote,time.monotonic(),(),True)
            raise
        if len(result)<=4:
            _ZIP_SESSION_CACHE=(
                root.remote,time.monotonic(),result,not bool(result))
        return result


def public_profile_fields(doc):
    if not isinstance(doc,dict):
        return {}
    return {key:doc.get(key) for key in (
        "platform","identity","handle","display_name","description",
        "followers_count","following_count","posts_count","fields",
        "created_at","indexed_at","captured_at","complete_media",
        "profile_url","pronouns","website","pinned_post","locked","bot",
        "header_description","avatar_description",
        "show_media","show_media_replies","show_featured")}


def sanitize_safe_link(value):
    if not isinstance(value,str) or len(value)>2048:
        return ""
    url=urlsplit(value)
    if (url.scheme!="https" or not url.hostname or url.username
            or url.password or url.fragment):
        return ""
    return value


# On the free 512MiB worker, opening the same saved account for
# profile/feed/media in parallel used to decrypt and SHA-verify the entire
# immutable ZIP history repeatedly, triggering verified Render OOM restarts.
# Reuse only successfully validated, account-bound bytes and serialize cold
# loads. Opt-in on the production Render container; offline tests and other
# runners remain unchanged.
_ARCHIVE_SESSION_LOCK=threading.RLock()
_ARCHIVE_SESSION_CACHE=None
ARCHIVE_SESSION_SECONDS=75


def open_account(account):
    global _ARCHIVE_SESSION_CACHE
    if os.getenv("DEMAND_ACCOUNT_VIEWER_SESSION_CACHE","0")!="1":
        return _open_account_uncached(account)
    with _ARCHIVE_SESSION_LOCK:
        cached=_ARCHIVE_SESSION_CACHE
        now=time.monotonic()
        if (cached is not None and cached[0]==account
                and now-cached[1]<ARCHIVE_SESSION_SECONDS):
            return cached[2]
        # Release OLD strong ZIP references BEFORE loading the next immutable
        # generation. Holding both old and new 200MiB+ histories during the
        # 75s rollover exceeded the 512MiB free instance.
        _ARCHIVE_SESSION_CACHE=None
        cached=None
        gc.collect()
        # Errors never populate the cache. Loading another account releases
        # the previous union, preventing N-account copies filling free RAM.
        result=_open_account_uncached(account)
        _ARCHIVE_SESSION_CACHE=(account,time.monotonic(),result)
        return result


def _open_account_uncached(account):
    match=REGISTRY_RE.fullmatch(account+".json")
    if not match:
        raise HTTPException(400,"Invalid archive account key")
    github=[]
    if github_temp_bundle.enabled():
        try:
            github=github_temp_bundle.matching_bundles(account)
            if not github:
                legacy=github_temp_bundle.account_bundle(account)
                if legacy is not None:
                    github=[legacy]
        except (RuntimeError,ValueError,TypeError,BundleInvalid):
            # A provider outage must not suppress already verified TeraBox.
            github=[]
    # Never elevate an unverified inventory hint to source object bytes.
    github=[bundle for bundle in github if isinstance(bundle,VerifiedBundle)]
    root=open_root()
    try:
        # A read-only union must include ALL available verified deltas.
        # Picking only the latest ZIP previously hid earlier immutable posts.
        bundle=next((item for item in _verified_account_bundles(root)
                     if account in item.accounts),None)
        combined=list(github)
        if bundle is not None and all(b.digest!=bundle.digest for b in combined):
            combined.append(bundle)
        if combined:
            return root if bundle is not None else None,combined[-1].accounts[account],(
                MergedBundleAccountCloud(combined))
        raw=root.read("metadata/target-accounts/"+account+".json",
                      cap=4000,optional=True)
        if raw is None:
            raise HTTPException(404,"Public account archive not registered")
        meta=json.loads(raw)
        if (not isinstance(meta,dict) or meta.get("platform")!=match.group(1)
                or archive_key(meta)!=match.group(2)):
            raise HTTPException(404,"Archive identity mismatch")
        return root,meta,account_cloud(root,meta)
    except (RuntimeError,TypeError,ValueError,KeyError):
        if github:
            return None,github[0].accounts[account],MergedBundleAccountCloud(github)
        raise HTTPException(502,"Private account archive read unavailable") from None


def latest_snapshot(archive,folder,pattern,cap=300_000):
    names=archive.names(folder)
    valid=sorted(n for n in names if pattern.fullmatch(n))
    if not valid:
        return None
    for name in valid[-3:][::-1]:
        raw=archive.read(folder+"/"+name,cap=cap,optional=True)
        if raw is None:
            continue
        try:
            item=json.loads(raw)
            if isinstance(item,dict):
                return item
        except (ValueError,TypeError):
            continue
    return None


PROFILE_SNAPSHOT_LIMIT=40


def profile_snapshot_history(archive,entry):
    """Read all bounded, immutable account-bound public profile snapshots.

    A newer unavailable banner never erases a verified previous snapshot.
    A newer explicitly not-set banner is intentional; historical artwork is
    accessible by selecting its dated snapshot, not silently shown as current.
    """
    names=sorted((name for name in archive.names("profile/snapshots")
                  if PROFILE_FILE_RE.fullmatch(name)),reverse=True)
    versions=[]
    for name in names[:PROFILE_SNAPSHOT_LIMIT]:
        raw=archive.read("profile/snapshots/"+name,cap=300_000,optional=True)
        if not raw:
            continue
        try:
            doc=json.loads(raw)
            if (not isinstance(doc,dict)
                or doc.get("identity")!=entry.get("identity")
                or doc.get("platform")!=entry.get("platform")):
                continue
            versions.append((name,doc))
        except (TypeError,ValueError):
            continue
    return versions


def profile_image_status(asset):
    if not isinstance(asset,dict):
        return "not_verified"
    status=str(asset.get("status") or "not_verified")
    return status if status in ("sha256_verified","unavailable","not_set") else "not_verified"


def profile_view(archive,account,entry,*,snapshot=""):
    versions=profile_snapshot_history(archive,entry)
    if snapshot and not PROFILE_FILE_RE.fullmatch(snapshot):
        raise HTTPException(400,"Invalid profile snapshot")
    selected=next(((n,d) for n,d in versions if n==snapshot),None) if snapshot else (
        versions[0] if versions else None)
    if selected is None:
        if snapshot:
            raise HTTPException(404,"Public profile snapshot unavailable")
        return {"available":False,"profile_url":
                sanitize_safe_link(entry.get("profile_url")),"history":[]}
    name,doc=selected
    view=public_profile_fields(doc)
    # Preserve the source provider's actual paragraph layout and verified
    # custom-field cards even for older saved snapshots whose generic
    # plain-text summary had concatenated separate <p> blocks.
    if doc.get("platform")=="mastodon":
        raw_profile=doc.get("raw") or {}
        if isinstance(raw_profile,dict):
            note=raw_profile.get("note")
            if isinstance(note,str):
                view["description"]=text_only(note)
            source_fields=raw_profile.get("fields",doc.get("fields",[]))
        else:
            source_fields=doc.get("fields",[])
        safe_fields=[]
        if isinstance(source_fields,list):
            for field in source_fields[:40]:
                if not isinstance(field,dict):continue
                field_name=str(field.get("name") or "")[:250]
                value=field.get("value") or ""
                parser=_PublicHtmlParts()
                if isinstance(value,str):
                    try:parser.feed(value[:12000])
                    except (ValueError,TypeError):pass
                pieces=[{"text":str(part.get("text") or "")[:1200],
                         "href":sanitize_safe_link(part.get("href"))}
                        for part in parser.parts[:50] if isinstance(part,dict)]
                if field_name or pieces:
                    safe_fields.append({"name":field_name,"parts":pieces,
                        "verified_at":field.get("verified_at")
                            if isinstance(field.get("verified_at"),str) else None})
        view["fields_rendered"]=safe_fields
    view["available"]=True
    view["profile_url"]=sanitize_safe_link(entry.get("profile_url"))
    view["snapshot_id"]=name
    view["latest_snapshot"]=bool(versions and name==versions[0][0])
    view["history"]=[{
        "id":n,"captured_at":d.get("captured_at"),
        "display_name":str(d.get("display_name") or "")[:100],
        "has_description":bool(d.get("description")),
        "assets":{kind:profile_image_status(
            (d.get("assets") or {}).get(kind))
            for kind in ("avatar","banner")}}
        for n,d in versions]
    view["assets"]={}
    view["asset_status"]={}
    for kind in ("avatar","banner"):
        asset=(doc.get("assets") or {}).get(kind)
        status=profile_image_status(asset)
        meta={"status":status}
        if status=="sha256_verified":
            tier=str(asset.get("source_tier") or "legacy_source_unclassified")
            meta.update({"source_tier":tier,"captured_at":doc.get("captured_at")})
            view["assets"][kind]=(
                "/api/account-archives/"+account+"/profile-asset/"+kind+
                "?snapshot="+name)
        else:
            view["assets"][kind]=None
        # Reuse earlier independently verified art ONLY when this current
        # source read was unavailable, never when the artist removed the art.
        if status in ("unavailable","not_verified") and not snapshot:
            for old_name,old_doc in versions[1:]:
                old_asset=(old_doc.get("assets") or {}).get(kind)
                if profile_image_status(old_asset)=="sha256_verified":
                    view["assets"][kind]=(
                        "/api/account-archives/"+account+"/profile-asset/"+
                        kind+"?snapshot="+old_name)
                    meta.update({"historical_fallback":True,
                                 "captured_at":old_doc.get("captured_at"),
                                 "source_tier":str(old_asset.get("source_tier") or
                                                   "legacy_source_unclassified")})
                    break
        view["asset_status"][kind]=meta
    return view


def archived_media_slot(pid,item):
    """Recover the original 0-based attachment position from its immutable key.

    A missing /media/0001 must never shift saved /media/0002 into slot zero.
    """
    if not isinstance(item,dict) or not isinstance(item.get("key"),str):
        return None
    match=re.fullmatch(
        r"posts/"+re.escape(pid)+r"/media/([0-9]{4})\.[a-z0-9]{1,8}",
        item["key"])
    if match is None:
        return None
    slot=int(match.group(1))-1
    return slot if 0<=slot<16 else None



class _PublicHtmlParts(HTMLParser):
    """Minimal safe Mastodon rich-text tokens, never provider HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.link=""
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            props=dict(attrs)
            self.link=sanitize_safe_link(props.get("href",""))
        elif tag in ("br","p"):
            self.parts.append({"text":"\n","href":""})
    def handle_endtag(self,tag):
        if tag=="a":self.link=""
        elif tag in ("p","div"):
            self.parts.append({"text":"\n","href":""})
    def handle_data(self,data):
        if data:self.parts.append({"text":data[:12000],"href":self.link})


def _safe_atproto_post_url(uri):
    if not isinstance(uri,str):
        return ""
    m=re.fullmatch(r"at://(did:plc:[a-z2-7]{24})/app.bsky.feed.post/([A-Za-z0-9_-]{3,100})",uri)
    return ("https://bsky.app/profile/"+m.group(1)+"/post/"+m.group(2)
            if m else "")


def _bsky_facet_parts(record,text):
    raw=text.encode("utf-8")
    facets=record.get("facets") or []
    if not isinstance(facets,list):
        return [{"text":text,"href":""}]
    links=[]
    for facet in facets[:100]:
        if not isinstance(facet,dict):continue
        span=facet.get("index") or {}
        if not isinstance(span,dict):continue
        begin=span.get("byteStart")
        end=span.get("byteEnd")
        if not (type(begin) is int and type(end) is int
                and 0<=begin<end<=len(raw)):continue
        href=""
        features=facet.get("features") or []
        if not isinstance(features,list):continue
        for feature in features[:4]:
            if not isinstance(feature,dict):continue
            kind=feature.get("$type")
            if kind=="app.bsky.richtext.facet#link":
                href=sanitize_safe_link(feature.get("uri"))
            elif kind=="app.bsky.richtext.facet#mention":
                did=feature.get("did","")
                if isinstance(did,str) and re.fullmatch(r"did:plc:[a-z2-7]{24}",did):
                    href="https://bsky.app/profile/"+did
            elif kind=="app.bsky.richtext.facet#tag":
                tag=feature.get("tag","")
                if isinstance(tag,str) and 0<len(tag)<=80:
                    href="https://bsky.app/hashtag/"+quote(tag,safe="")
            if href:break
        if href:links.append((begin,end,href))
    links.sort()
    parts=[]
    cursor=0
    for begin,end,href in links:
        if begin<cursor:continue
        if begin>cursor:
            parts.append({"text":raw[cursor:begin].decode("utf-8","replace"),"href":""})
        parts.append({"text":raw[begin:end].decode("utf-8","replace"),"href":href})
        cursor=end
    if cursor<len(raw):
        parts.append({"text":raw[cursor:].decode("utf-8","replace"),"href":""})
    return parts or [{"text":text,"href":""}]


def _source_ui(archive,post):
    """Reconstruct only UI details saved with this exact immutable post.

    Never fetch a live SNS during archival viewing, or invent missing
    captions, engagement numbers, screenshots, quoted content or poll votes.
    """
    out={"rich_text":[],"content_warning":"","sensitive":False,
         "alt_text":[],"external_card":None,"quoted_post":None,
         "poll":None,"reblog":None,"engagement":None,"pinned":False,
         "source_labels":[]}
    pid=post.get("id","")
    if not HEX40.fullmatch(str(pid)):
        return out
    try:
        raw=archive.read("metadata/source-records/"+pid+".json",
                         cap=3_000_000,optional=True)
        source=json.loads(raw) if raw else None
    except (RuntimeError,ValueError,TypeError,KeyError,AttributeError):
        # In-memory search-only test journals and historic lightweight
        # catalog readers expose no source-record API. Keep their already
        # SHA-verified post text and never invent extra provider metadata.
        source=None
    if not isinstance(source,dict):return out
    text=str(post.get("text") or "")
    if post.get("platform")=="bluesky":
        if source.get("uri")!=post.get("original_id"):
            # An edited immutable logical record has its own source snapshot
            # but retains the original ATProto URI.
            return out
        record=source.get("value")
        if not isinstance(record,dict):return out
        out["rich_text"]=_bsky_facet_parts(record,text)
        labels=record.get("labels") or {}
        values=labels.get("values",[]) if isinstance(labels,dict) else []
        if isinstance(values,list):
            out["source_labels"]=[
                str(v.get("val"))[:80] for v in values[:100]
                if isinstance(v,dict) and isinstance(v.get("val"),str)]
        if isinstance(values,list) and any(
                isinstance(x,dict) and x.get("val") in
                ("porn","sexual","nudity","graphic-media") for x in values):
            out["sensitive"]=True
            out["content_warning"]="게시자가 지정한 민감 콘텐츠"
        embed=record.get("embed") or {}
        if isinstance(embed,dict):
            item=embed.get("media") if embed.get("$type")=="app.bsky.embed.recordWithMedia" else embed
            if isinstance(item,dict):
                illustrations=item.get("images",[])
                if isinstance(illustrations,list):
                    out["alt_text"]=[str(x.get("alt") or "")[:1600] if isinstance(x,dict)
                                     else "" for x in illustrations[:16]]
                ext=item.get("external")
                if isinstance(ext,dict):
                    url=sanitize_safe_link(ext.get("uri"))
                    if url:
                        out["external_card"]={
                           "url":url,"title":str(ext.get("title") or "")[:300],
                           "description":str(ext.get("description") or "")[:500]}
            record_ref=(embed.get("record") or {})
            if isinstance(record_ref,dict):
                nested=record_ref.get("record") if isinstance(record_ref.get("record"),dict) else record_ref
                link=_safe_atproto_post_url(nested.get("uri"))
                if link:out["quoted_post"]={"url":link}
    elif post.get("platform")=="mastodon":
        published=source.get("id")
        if not isinstance(published,(str,int)) or (
                ":"+str(published)!=str(post.get("original_id",""))[-len(str(published))-1:]):
            return out
        embedded=source.get("reblog")
        display=embedded if isinstance(embedded,dict) and embedded.get("visibility") in ("public","unlisted") else source
        if embedded and display is embedded:
            owner=display.get("account") or {}
            if isinstance(owner,dict):
                out["reblog"]={
                    "name":str(owner.get("display_name") or owner.get("acct") or "")[:200],
                    "handle":str(owner.get("acct") or "")[:200],
                    "url":sanitize_safe_link(owner.get("url"))}
        markup=display.get("content") or ""
        if isinstance(markup,str):
            parser=_PublicHtmlParts()
            try:
                parser.feed(markup[:100_000])
                out["rich_text"]=parser.parts[:300]
            except (TypeError,ValueError):
                pass
        out["pinned"]=bool(source.get("pinned"))
        warning=display.get("spoiler_text") or source.get("spoiler_text") or ""
        out["content_warning"]=str(warning)[:1000]
        out["sensitive"]=bool(source.get("sensitive") or display.get("sensitive") or warning)
        media=display.get("media_attachments") or []
        if isinstance(media,list):
            out["alt_text"]=[str(m.get("description") or "")[:1600]
                             if isinstance(m,dict) else "" for m in media[:16]]
        card=display.get("card")
        if isinstance(card,dict):
            link=sanitize_safe_link(card.get("url"))
            if link:
                out["external_card"]={"url":link,
                    "title":str(card.get("title") or "")[:300],
                    "description":str(card.get("description") or "")[:500]}
        poll=display.get("poll")
        if isinstance(poll,dict) and isinstance(poll.get("options"),list):
            out["poll"]={"multiple":poll.get("multiple") is True,
                         "expired":poll.get("expired") is True,
                         "options":[{"title":str(option.get("title") or "")[:250],
                             "votes_count":option.get("votes_count")
                                if type(option.get("votes_count")) is int else None}
                          for option in poll["options"][:20]
                          if isinstance(option,dict)]}
        out["engagement"]={
            name:display.get(name) if type(display.get(name)) is int else None
            for name in ("replies_count","reblogs_count","favourites_count")}
    if not out["rich_text"]:
        out["rich_text"]=[{"text":text,"href":""}]
    return out



def feed_data(archive,account,offset,limit,q="",kind="",media_status=""):
    """Filter the COMPLETE verified account journal before pagination.

    Never search only the currently displayed page. Keep the original media
    indices, including unverified slots, so missing source photos cannot slide
    into another attachment position in the private SNS-style reader.
    """
    rows=archive.load_catalog(include_entries=True)
    matching=[]
    needle=q.strip().casefold()
    for post in rows:
        if not isinstance(post,dict) or not HEX40.fullmatch(str(post.get("id",""))):
            continue
        text=str(post.get("text") or "")
        if needle and needle not in text.casefold():
            continue
        category=("revision" if post.get("revision_of") else
                  "reply" if post.get("kind")=="reply" else "post")
        if kind:
            if kind=="activity_posts_boosts" and category not in ("post","reblog"):
                continue
            elif kind=="activity_posts_replies" and category not in ("post","reply"):
                continue
            elif kind=="activity_all" and category not in ("post","reply","reblog"):
                continue
            elif kind=="featured":
                if not _source_ui(archive,post).get("pinned"):continue
            elif kind not in ("activity_posts_boosts","activity_posts_replies","activity_all","featured") and category!=kind:
                continue
        expected=post.get("media_expected",0)
        saved=post.get("media_saved",0)
        if not isinstance(expected,int) or expected<0:expected=0
        if not isinstance(saved,int) or saved<0:saved=0
        complete=post.get("archive_complete") is True and saved>=expected
        # Native SNS media tab includes only entries with a real archived
        # source media slot, never text-only posts or fabricated thumbnails.
        if media_status in ("has_media","has_video"):
            raw_slots=post.get("media",[])
            if not isinstance(raw_slots,list) or not any(
                    isinstance(item,dict) and
                    archived_media_slot(str(post["id"]),item) is not None
                    and (media_status=="has_media" or
                         str(item.get("mime","")).startswith("video/"))
                    for item in raw_slots[:16]):
                continue
        elif media_status and media_status!=("complete" if complete else "partial"):
            continue
        pid=post["id"]
        media=[]
        source=post.get("media",[])
        if not isinstance(source,list):source=[]
        known_slots=set()
        for item in source[:16]:
            index=archived_media_slot(pid,item)
            if index is None or index in known_slots:
                continue
            known_slots.add(index)
            verified=item.get("remote_verified") is True
            media.append({
                "index":index,
                "kind":item.get("kind","image"),
                "mime":item.get("mime",""),
                "bytes":item.get("bytes",0),
                "url":("/api/account-archives/"+account+"/media/"+pid+"/"+str(index))
                        if verified else None,
                "verified_sha256":bool(verified)})
        media.sort(key=lambda value:value["index"])
        matching.append({
            "id":pid,"original_id":post.get("original_id"),
            "platform":post.get("platform"),
            "posted_at":post.get("posted_at"),"text":text,
            "source_url":sanitize_safe_link(post.get("source_url")),
            "profile_url":sanitize_safe_link(post.get("profile_url")),
            "kind":post.get("kind","post"),
            "revision_of":post.get("revision_of",""),
            "captured_at":post.get("captured_at",""),
            "reply_to":post.get("reply_to",""),
            "media":media,"media_expected":expected,
            "media_saved":saved,"archive_complete":complete})
    page=matching[offset:offset+limit]
    # Parse rich text, source warnings and embeds ONLY for the requested
    # page, not for a 900-post whole-account search on every tab change.
    for post in page:
        post.update(_source_ui(archive,post))
    return {"total":len(matching),"offset":offset,"limit":limit,
            "posts":page,"more":offset+limit<len(matching)}


def graph_data(archive,kind,offset,limit):
    page_names=sorted((int(m.group(2)),n) for n in archive.names("graph/pages")
                      if (m:=GRAPH_PAGE.fullmatch(n)) and m.group(1)==kind)
    merged=[]
    known=set()
    # Retain account records in public edge order; each page has a source
    # snapshot timestamp and remains immutable for history/reconciliation.
    for _seq,name in page_names:
        raw=archive.read("graph/pages/"+name,cap=100_000,optional=True)
        if raw is None:
            continue
        try:
            value=json.loads(raw)
            items=value.get("items",[])
            if not isinstance(items,list):
                continue
            for user in items:
                if not isinstance(user,dict):
                    continue
                key=str(user.get("id",""))
                if not key or key in known: continue
                known.add(key)
                merged.append({"id":key,"handle":str(user.get("handle",""))[:200],
                               "display_name":str(user.get("display_name",""))[:300],
                               "profile_url":sanitize_safe_link(user.get("profile_url"))})
        except (ValueError,TypeError):
            continue
    return {"kind":kind,"captured_unique":len(merged),
            "source_pages":len(page_names),"offset":offset,"limit":limit,
            "accounts":merged[offset:offset+limit],
            "more":offset+limit<len(merged),
            "full_network_coverage_guaranteed":False}


def get_verified_media(archive,item,request):
    key=item.get("key");digest=item.get("sha256")
    length=item.get("bytes");mime=item.get("mime")
    if not (isinstance(key,str) and isinstance(digest,str)
            and re.fullmatch(r"[a-f0-9]{64}",digest)
            and isinstance(length,int) and 0<length<=80_000_000
            and item.get("remote_verified",True) is True):
        raise HTTPException(404,"Original media not verified")
    try:
        raw=archive.read_verified(key,digest,cap=length+1)
    except (RuntimeError,ValueError):
        raw=None
    if raw is None or len(raw)!=length:
        raise HTTPException(502,"Archived media SHA readback unavailable")
    # Safari requires byte ranges for video; validate the request strictly.
    range_value=request.headers.get("range","")
    if range_value:
        m=re.fullmatch(r"bytes=(\d*)-(\d*)",range_value)
        if not m or (not m.group(1) and not m.group(2)):
            raise HTTPException(416,"Invalid media range")
        if m.group(1):
            start=int(m.group(1))
            end=min(int(m.group(2)),len(raw)-1) if m.group(2) else len(raw)-1
        else:
            suffix=int(m.group(2))
            start=max(0,len(raw)-suffix)
            end=len(raw)-1
        if start>=len(raw) or end<start:
            raise HTTPException(416,"Unsatisfiable media range")
        return Response(raw[start:end+1],status_code=206,media_type=mime,
                        headers={**CACHE_HEADERS,"Accept-Ranges":"bytes",
                                 "Content-Range":f"bytes {start}-{end}/{len(raw)}"})
    return Response(raw,media_type=mime,
                    headers={**CACHE_HEADERS,"Accept-Ranges":"bytes"})


def account_picker_details(entry,archive=None):
    """Return only source-verified nickname/handle for the private chooser.

    Profile snapshot names live inside the already SHA-verified account ZIP.
    This neither calls a live SNS API nor infers links between identities.
    """
    if not isinstance(entry,dict):
        return {"display_name":"","handle":"","profile_snapshot_verified":False}
    profile=None
    if archive is not None:
        try:
            snapshot=latest_snapshot(archive,"profile/snapshots",PROFILE_FILE_RE)
            if (isinstance(snapshot,dict)
                    and snapshot.get("identity")==entry.get("identity")
                    and snapshot.get("platform")==entry.get("platform")):
                profile=snapshot
        except (RuntimeError,ValueError,KeyError,TypeError):
            pass
    def short(value,limit):
        return " ".join(str(value).split())[:limit] if isinstance(value,str) else ""
    trusted=profile if profile is not None else entry
    name=short(trusted.get("display_name"),100)
    handle=short(trusted.get("handle"),200).lstrip("@")
    if not handle:
        url=sanitize_safe_link(entry.get("profile_url"))
        part=urlsplit(url)
        path=part.path.rstrip("/").split("/")
        if part.hostname=="bsky.app" and len(path)>=3 and path[-2]=="profile":
            candidate=path[-1]
            if not candidate.startswith("did:") and len(candidate)<=200:
                handle=candidate
        elif part.hostname and path[-1].startswith("@"):
            handle=path[-1].lstrip("@")+"@"+part.hostname
    return {"display_name":name,"handle":handle,
            "profile_snapshot_verified":profile is not None
                   and isinstance(archive,BundleAccountCloud)}


def bundled_account_picker_row(bundle,account,*,temporary):
    """Build label metadata from the exact verified ZIP already in memory."""
    entry=bundle.accounts[account]
    # Historic partial receipts may expose only the signed account metadata.
    # Real verified ZIPs always provide prefix/items; never invent a nickname.
    archive=(BundleAccountCloud(bundle)
             if hasattr(bundle,"prefix") and hasattr(bundle,"items") else None)
    identity=account_picker_details(entry,archive)
    return {"key":account,"platform":entry["platform"],
            "profile_url":sanitize_safe_link(entry.get("profile_url")),
            "backup_kind":"github_temp_sha_verified" if temporary
                          else "terabox_zip_sha_verified",
            "posts_verified_in_bundle":bundle.post_count,
            "objects_verified_in_bundle":bundle.object_count,
            "source_state":bundle.source_state,
            "temporary":bool(temporary),**identity}


# VERIFIED 2026-11-18 Render event: 512 MiB OOM-killed the worker when
# many distinct archive ZIP chains were read simultaneously. Per-account
# cache locks protect loading, but a finished load stays referenced until
# each HTTP response finishes. Bound the entire expensive request lifetime.
# Saturation returns a *truthful* retryable 503, not false missing originals.
_ARCHIVE_READ_SLOT=threading.BoundedSemaphore(value=1)
_ARCHIVE_READ_WAIT_SECONDS=5.0

def archive_read_capacity():
    if not _ARCHIVE_READ_SLOT.acquire(timeout=_ARCHIVE_READ_WAIT_SECONDS):
        raise HTTPException(status_code=503,
            detail="Archive capacity busy; retry preserved originals",
            headers={"Retry-After":"3","Cache-Control":"private, no-store"})
    try:
        yield
    finally:
        _ARCHIVE_READ_SLOT.release()


def create_router(auth):
    # CloudArchive uses blocking rclone subprocesses. FastAPI dispatches these
    # sync GET handlers to its worker pool, keeping health, receipts and queue
    # admission responsive while a remote original is read and SHA-checked.
    router=APIRouter()

    @router.get("/account-archive",include_in_schema=False)
    def viewer(request:Request):
        auth(request)
        return FileResponse(VIEW_DIR/"account_archive_view.html",
                            media_type="text/html; charset=utf-8",
                            headers={**CACHE_HEADERS,
                                     "Content-Security-Policy":
                                     "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"})

    @router.get("/account-archive/{asset_name}",include_in_schema=False)
    def asset(request:Request,asset_name:str):
        auth(request)
        if asset_name not in ("account_archive_view.js","account_archive_view.css"):
            raise HTTPException(404,"Unknown viewer asset")
        mime="application/javascript" if asset_name.endswith(".js") else "text/css"
        return FileResponse(VIEW_DIR/asset_name,media_type=mime,headers=CACHE_HEADERS)

    @router.get("/api/account-archives")
    def accounts(request:Request):
        auth(request)
        if github_temp_bundle.enabled():
            data=[]
            github_failed=False
            terabox_failed=False
            # Existing independently AES/SHA-verified archive discovery lives
            # in a durable owner-only registry, not the truncated Atom feed.
            # This is an inventory hint. Content GETs always verify originals.
            try:
                from backup_queue import archive_index_rows
                rows=archive_index_rows()
                data=[{
                    "key":row["account_key"],"platform":row["platform"],
                    "profile_url":sanitize_safe_link(row.get("profile_url")),
                    "display_name":str(row.get("display_name") or "")[:100],
                    "handle":str(row.get("handle") or "")[:200],
                    "backup_kind":"github_temp_sha_verified",
                    "posts_verified_in_bundle":int(row.get("posts_verified",0)),
                    "objects_verified_in_bundle":int(row.get("objects_verified",0)),
                    "source_state":"PREVIOUSLY_VERIFIED_RELEASE_INDEX",
                    "profile_snapshot_verified":bool(
                        row.get("display_name") or row.get("handle")),
                    "temporary":True,
                    "index_requires_original_recheck":True}
                    for row in rows]
            except (RuntimeError,ValueError,TypeError,KeyError):
                data=[]
            if not data:
                try:
                    data=[bundled_account_picker_row(bundle,bundle.account,
                                                    temporary=True)
                          for bundle in github_temp_bundle.latest_bundles()]
                except (RuntimeError,ValueError,TypeError,BundleInvalid):
                    github_failed=True
                try:
                    root=open_root()
                    index={item["key"]:item for item in data}
                    for bundle in _verified_account_bundles(root):
                        for account,entry in bundle.accounts.items():
                            present=index.get(account)
                            if (present is not None and bundle.post_count<=
                                    present["posts_verified_in_bundle"]):
                                continue
                            row=bundled_account_picker_row(bundle,account,
                                                          temporary=False)
                            if present is None:
                                data.append(row)
                            else:
                                present.update(row)
                            index[account]=present if present is not None else row
                except (RuntimeError,ValueError,TypeError,KeyError,BundleInvalid):
                    terabox_failed=True
            if not data and github_failed and terabox_failed:
                raise HTTPException(502,"Both verified account indexes unavailable")
            return JSONResponse({"accounts":data},headers=CACHE_HEADERS)
        root=open_root()
        try:
            # Legacy nested per-record paths can return copyto/lsf missing
            # even when a complete ZIP is remotely SHA-verified. Do not let
            # a broken old registry hide the independently verified backups.
            try:
                names=root.names("metadata/target-accounts")
            except RuntimeError:
                names=[]
            data=[]
            for name in names:
                if not REGISTRY_RE.fullmatch(name):
                    continue
                try:
                    raw=root.read("metadata/target-accounts/"+name,cap=4000,optional=True)
                    if raw is None:continue
                    entry=json.loads(raw)
                    if (entry.get("platform")+"-"+archive_key(entry)+".json")!=name:
                        continue
                    data.append({"key":name[:-5],"platform":entry["platform"],
                                 "profile_url":sanitize_safe_link(entry.get("profile_url")),
                                 **account_picker_details(entry,account_cloud(root,entry))})
                except (RuntimeError,ValueError,KeyError,TypeError):
                    continue
            seen={item["key"] for item in data}
            # ZIP receipts are independently re-read and verified against the
            # embedded 64-digit hashes, not inferred from GitHub green checks.
            for bundle in available_bundles(root):
                for account,entry in bundle.accounts.items():
                    if account in seen:
                        for row in data:
                            if row["key"]==account:
                                row["backup_kind"]="terabox_zip_sha_verified"
                                row["posts_verified_in_bundle"]=bundle.post_count
                                row["objects_verified_in_bundle"]=bundle.object_count
                                row.update(account_picker_details(
                                    bundle.accounts[account],BundleAccountCloud(bundle)))
                        continue
                    seen.add(account)
                    data.append(bundled_account_picker_row(
                        bundle,account,temporary=False))
            return JSONResponse({"accounts":data},headers=CACHE_HEADERS)
        except (RuntimeError,TypeError,ValueError,KeyError):
            raise HTTPException(502,"Private account index unavailable") from None

    @router.get("/api/account-archives/{account}/backup-status",dependencies=[Depends(archive_read_capacity)])
    def backup_status(request:Request,account:str):
        auth(request)
        _,_,archive=open_account(account)
        if isinstance(archive,BundleAccountCloud):
            bundle=archive.bundle
            # An append-only incremental ZIP may contain zero NEW posts
            # while older, independently SHA-verified ancestor ZIPs contain
            # the complete saved feed. Count UNIQUE verified object keys in
            # the merged reader, not the latest delta's post_count.
            history=(archive.bundles if isinstance(
                archive,MergedBundleAccountCloud) else (bundle,))
            keys={key for part in history for key in part.items}
            prefix=archive.prefix+"posts/"
            post_keys={key for key in keys if
                       key.startswith(prefix) and key.endswith("/post.json")}
            source_kinds={bool(getattr(part,"temporary",False))
                          for part in history}
            storage=("mixed_verified_zip_sources" if len(source_kinds)>1 else
                     "github_encrypted_temporary" if True in source_kinds
                     else "private_terabox")
            return JSONResponse({
                "storage":storage,
                "state":"REMOTE_ZIP_SHA_VERIFIED",
                "source_state":bundle.source_state,
                "original_objects":len(keys),
                "public_posts":len(post_keys),
                "latest_zip_public_posts":bundle.post_count,
                "verified_history_zips":len(history),
                "recorded_at":bundle.recorded_at,
                "full_historical_coverage_guaranteed":False,
            },headers=CACHE_HEADERS)
        return JSONResponse({
            "storage":"private_terabox",
            "state":"LEGACY_PER_RECORD",
            "full_historical_coverage_guaranteed":False,
        },headers=CACHE_HEADERS)

    @router.get("/api/account-archives/{account}/profile",dependencies=[Depends(archive_read_capacity)])
    def profile(request:Request,account:str,
                snapshot:str=Query("",max_length=80)):
        auth(request)
        _,entry,archive=open_account(account)
        try:
            return JSONResponse(profile_view(archive,account,entry,snapshot=snapshot),
                                headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError,KeyError):
            raise HTTPException(502,"Archived public profile unavailable") from None

    @router.get("/api/account-archives/{account}/feed",dependencies=[Depends(archive_read_capacity)])
    def feed(request:Request,account:str,
                   offset:int=Query(0,ge=0,le=200000),
                   limit:int=Query(20,ge=1,le=50),
                   q:str=Query("",max_length=100),
                   kind:str=Query(""),
                   media_status:str=Query("")):
        auth(request)
        if kind not in ("","post","reply","reblog","revision",
                         "activity_posts_boosts","activity_posts_replies",
                         "activity_all","featured"):
            raise HTTPException(400,"Invalid archived post type")
        if media_status not in ("","complete","partial","has_media","has_video"):
            raise HTTPException(400,"Invalid media verification filter")
        _,_,archive=open_account(account)
        try:
            return JSONResponse(feed_data(archive,account,offset,limit,
                                          q=q,kind=kind,media_status=media_status),
                                headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Account history read unavailable") from None

    @router.get("/api/account-archives/{account}/graph/{kind}",dependencies=[Depends(archive_read_capacity)])
    def graph(request:Request,account:str,kind:str,
                    offset:int=Query(0,ge=0,le=200000),
                    limit:int=Query(50,ge=1,le=100)):
        auth(request)
        if kind not in ("followers","following"):
            raise HTTPException(400,"Invalid public graph")
        _,_,archive=open_account(account)
        try:
            return JSONResponse(graph_data(archive,kind,offset,limit),
                                headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Public graph archive unavailable") from None

    @router.get("/api/account-archives/{account}/threads/{pid}",dependencies=[Depends(archive_read_capacity)])
    def thread(request:Request,account:str,pid:str):
        auth(request)
        if not HEX40.fullmatch(pid):
            raise HTTPException(400,"Invalid post")
        _,_,archive=open_account(account)
        try:
            data=latest_snapshot(archive,"threads/"+pid,THREAD_FILE_RE,cap=500_000)
            if not data:
                return JSONResponse({"captured":False,"replies":[]},headers=CACHE_HEADERS)
            out=[]
            for r in data.get("replies",[])[:120]:
                if not isinstance(r,dict):continue
                out.append({"id":r.get("id"),"author":r.get("author"),
                            "display_name":r.get("display_name"),
                            "text":r.get("text"),"posted_at":r.get("posted_at"),
                            "source_url":sanitize_safe_link(r.get("uri")),
                            "media_source_links":[sanitize_safe_link(v)
                                    for v in r.get("media_urls",[])[:16]
                                    if sanitize_safe_link(v)]})
            return JSONResponse({"captured":True,"replies":out,
                                 "truncated":bool(data.get("truncated")),
                                 "captured_at":data.get("captured_at"),
                                 "comment_media_backed_up":False},headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Public reply archive unavailable") from None

    @router.get("/api/account-archives/{account}/media/{pid}/{index}",dependencies=[Depends(archive_read_capacity)])
    def post_media(request:Request,account:str,pid:str,index:int):
        auth(request)
        if not HEX40.fullmatch(pid) or index<0 or index>=16:
            raise HTTPException(400,"Invalid original media")
        _,_,archive=open_account(account)
        try:
            posts=archive.load_catalog()
            post=next((p for p in posts if p.get("id")==pid),None)
            if not post or not isinstance(post.get("media"),list):
                raise HTTPException(404,"Media not archived")
            media=next((item for item in post["media"]
                        if archived_media_slot(pid,item)==index),None)
            if media is None:
                raise HTTPException(404,"Original attachment position not saved")
            return get_verified_media(archive,media,request)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Original media read unavailable") from None

    @router.get("/api/account-archives/{account}/profile-asset/{kind}",dependencies=[Depends(archive_read_capacity)])
    def profile_asset(request:Request,account:str,kind:str,
                      snapshot:str=Query("",max_length=80)):
        auth(request)
        if kind not in ("avatar","banner"):
            raise HTTPException(400,"Invalid profile media")
        if snapshot and not PROFILE_FILE_RE.fullmatch(snapshot):
            raise HTTPException(400,"Invalid profile snapshot")
        _,entry,archive=open_account(account)
        versions=profile_snapshot_history(archive,entry)
        doc=next((row for n,row in versions if n==snapshot),None) if snapshot else (
            versions[0][1] if versions else None)
        if doc is None:
            raise HTTPException(404,"Profile snapshot unavailable")
        asset=(doc.get("assets") or {}).get(kind) or {}
        if (asset.get("status")!="sha256_verified"
                or not str(asset.get("key","")).startswith("profile/assets/")):
            raise HTTPException(404,"Profile image not archived")
        return get_verified_media(archive,
                                  {**asset,"remote_verified":True},request)

    return router
