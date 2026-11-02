"""Independent aggregate-only checks of additional free public social discovery.

Goal: test direct account/tag pages, cross-post URL discovery through Bluesky,
and a few public source adapters beyond the existing X/Threads/Instagram
web-index + original-reader implementation.

All checks are small, public and anonymous. They log NO usernames, post text,
IDs, URLs, media, authentication or exact examples. We neither download media
nor bypass auth, CAPTCHAs or rate controls. This is research, not bulk ingestion.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
import urllib.error

TERMS=("뒷계","섹트","일탈계")
UA="IntersectionPublicMethodResearch/1.0 (+https://github.com/koith/browser-app-lab)"
REGEX=re.compile(r"https?://(?:www\.)?(?:x\.com|twitter\.com|threads\.(?:com|net)|instagram\.com)/[^\s<>\"']+",re.I)
SOURCE_DOMAINS={
 "x.com":"x","twitter.com":"x","threads.com":"threads","threads.net":"threads",
 "instagram.com":"instagram"
}
PATHS={"x":re.compile(r"^/[^/]+/status/[0-9]+"),"threads":re.compile(r"^/@[^/]+/post/[A-Za-z0-9_-]+"),
"instagram":re.compile(r"^/(?:p|reel)/[A-Za-z0-9_-]+")}
class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__();self.meta={};self.script_types={};self.script=False;self.body=[];self.scripts=[]
    def handle_starttag(self,tag,attrs):
        att=dict(attrs)
        if tag=="meta":
            name=att.get("property") or att.get("name")
            if name in ("og:title","og:description","og:image","article:published_time","description"):
                self.meta[name]=att.get("content") or ""
        if tag=="script" and (att.get("type") in ("application/ld+json","application/json")):
            self.script=True;self.body=[];self.script_type=att.get("type")
    def handle_data(self,data):
        if self.script:self.body.append(data)
    def handle_endtag(self,tag):
        if tag=="script" and self.script:
            self.scripts.append((self.script_type,"".join(self.body)))
            self.script=False;self.body=[]
def get(url,accept="application/json, text/html",cap=2000000):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
    try:
        with urllib.request.urlopen(req,timeout=12) as res:
            return res.status,res.read(cap).decode("utf-8","replace"),""
    except urllib.error.HTTPError as e:return e.code,"","HTTP denied"
    except Exception as e:return 0,"",type(e).__name__
def canonical(link):
    try:
        p=urllib.parse.urlsplit(link)
        host=(p.hostname or "").lower().removeprefix("www.")
        kind=SOURCE_DOMAINS.get(host)
        if not kind or p.scheme not in ("http","https") or not PATHS[kind].match(p.path):
            return None
        return kind
    except (ValueError,TypeError):return None
def bluesky(term):
    url="https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?"+urllib.parse.urlencode({"q":term,"limit":80,"sort":"latest"})
    status,body,err=get(url,cap=2300000)
    out={"method":"bluesky_external_crosspost_discovery","term":"t"+str(TERMS.index(term)+1),
         "http":status,"error":err}
    try:
        data=json.loads(body);items=data.get("posts",[])
        seen=set();matching=0;linked=0;counts={k:0 for k in ("x","threads","instagram")}
        for p in items if isinstance(items,list) else []:
            if not isinstance(p,dict):continue
            record=p.get("record") if isinstance(p.get("record"),dict) else {}
            text=str(record.get("text") or "")
            matching+=int(term in text)
            links=REGEX.findall(text)
            fac=record.get("facets",[])
            for f in fac if isinstance(fac,list) else []:
                for feature in f.get("features",[]) if isinstance(f,dict) else []:
                    if isinstance(feature,dict) and feature.get("uri"):links.append(str(feature["uri"]))
            embed=p.get("embed") if isinstance(p.get("embed"),dict) else {}
            external=embed.get("external") if isinstance(embed.get("external"),dict) else {}
            if external.get("uri"):links.append(str(external["uri"]))
            found=set(filter(None,(canonical(link) for link in links)))
            if found:linked+=1
            for k in found:counts[k]+=1
        out.update(posts_returned=len(items),keyword_exact_text=matching,
                   posts_with_canonical_external_sns_link=linked,
                   linked_x=counts["x"],linked_threads=counts["threads"],linked_instagram=counts["instagram"])
    except (ValueError,TypeError,AttributeError):out["invalid_json"]=True
    return out
def instagram_profile(account):
    status,body,error=get("https://www.instagram.com/api/v1/users/web_profile_info/?"+
       urllib.parse.urlencode({"username":account}),cap=2300000)
    out={"method":"instagram_anon_public_profile_json","profile":"control1" if account=="nasa" else "control2",
         "http":status,"error":error}
    if not body:return out
    try:
        data=json.loads(body)
        u=data.get("data",{}).get("user",{})
        edges=((u.get("edge_owner_to_timeline_media") or {}).get("edges") or [])
        out.update(profile_object=bool(u.get("id")),private=u.get("is_private"),
                   media_items=len(edges),
                   with_caption=sum(bool(e.get("node",{}).get("edge_media_to_caption",{}).get("edges")) for e in edges if isinstance(e,dict)),
                   with_timestamp=sum(bool(e.get("node",{}).get("taken_at_timestamp")) for e in edges if isinstance(e,dict)))
    except Exception:out["json_parse_failed"]=True
    return out
def instagram_page(account):
    status,body,error=get("https://www.instagram.com/"+account+"/",accept="text/html",cap=900000)
    out={"method":"instagram_anon_public_profile_html","profile":"control1","http":status,"error":error,
         "html_bytes":len(body)}
    if body:
        h=MetaParser()
        try:h.feed(body)
        except Exception:pass
        out.update(og_description=bool(h.meta.get("og:description")),
                   og_image=bool(h.meta.get("og:image")),
                   embedded_json_count=len(h.scripts),
                   schema_org_json_ld=sum(t=="application/ld+json" for t,_ in h.scripts))
    return out
def mastodon_hashtag(term):
    code,body,err=get("https://mastodon.social/api/v1/timelines/tag/"+urllib.parse.quote(term,safe="")+"?limit=10")
    out={"method":"mastodon_public_hashtag","term":"control" if term=="coffee" else "project",
         "http":code,"error":err}
    try:
        rows=json.loads(body)
        if isinstance(rows,list):
            out.update(status_count=len(rows),dated=sum(bool(r.get("created_at")) for r in rows if isinstance(r,dict)),
                       keyword_in_content=sum(term in str(r.get("content","")) for r in rows if isinstance(r,dict)))
    except Exception:out["valid_json"]=False
    return out
def telegram_preview():
    status,body,error=get("https://t.me/s/telegram",accept="text/html",cap=1300000)
    return {"method":"telegram_public_channel_preview","http":status,"error":error,
            "public_message_blocks":len(re.findall(r"data-post=",body)),"html_bytes":len(body)}
def arctic_reddit():
    params=urllib.parse.urlencode({"title":"coffee","after":"2026-10-28","limit":5,"sort":"desc"})
    status,body,error=get("https://arctic-shift.photon-reddit.com/api/posts/search?"+params)
    out={"method":"arctic_shift_reddit_title_date_search","http":status,"error":error}
    try:
        obj=json.loads(body)
        data=obj.get("data",[]) if isinstance(obj,dict) else []
        out.update(results=len(data),source_timestamps=sum(bool(p.get("created_utc")) for p in data if isinstance(p,dict)))
    except Exception:out["valid_json"]=False
    return out
TASKS=[(bluesky,(x,)) for x in TERMS]
TASKS+= [(instagram_profile,("nasa",)),(instagram_profile,("instagram",)),
         (instagram_page,("nasa",)),(mastodon_hashtag,("coffee",)),
         (mastodon_hashtag,("뒷계",)),(telegram_preview,()),(arctic_reddit,())]
if __name__=="__main__":
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(lambda a:a[0](*a[1]),TASKS):
            print(json.dumps(result,ensure_ascii=False),flush=True)
