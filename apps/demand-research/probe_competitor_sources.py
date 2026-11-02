"""Benchmark peer-service collection methods against real public sources.

Adapted from *documented approach*, not copied source code:
- RSSHub Threads search reads public HTML embedded JSON post fields.
- RSSHub hosted RSS endpoint can deliver items, dates and enclosure links.
- RSS-Bridge philosophy: profile/index page with open graph metadata.
- Pixelfed/Mastodon: standard ActivityPub-style public hashtag timeline.

Safety: aggregate diagnostics only, ≤10 requests, no login, no auth cookie,
no proxy/challenge bypass, no raw public post/author/URL/media retention.
"""
from __future__ import annotations
import concurrent.futures
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

QUERIES={"control":"커피","project":"일탈계"}
UA="IntersectionPublicSourceMethodValidation/1.0 (+https://github.com/koith/browser-app-lab)"
LIMIT=3_800_000

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active=False
        self.text=[]
        self.scripts=[]
        self.og={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="script" and ("data-sjs" in a or a.get("type")=="application/json"):
            self.active=True;self.text=[]
        if tag=="meta" and a.get("property","").startswith("og:"):
            self.og[a["property"]]=a.get("content","")
    def handle_data(self,data):
        if self.active:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=="script" and self.active:
            self.scripts.append("".join(self.text))
            self.active=False;self.text=[]

def fetch(url,accept="text/html"):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
    try:
        with urllib.request.urlopen(req,timeout=15) as r:
            return r.status,r.read(LIMIT).decode("utf-8","replace"),""
    except urllib.error.HTTPError as e:
        return e.code,"", "HTTP denied"
    except Exception as e:
        return 0,"",type(e).__name__

def collect_posts(data):
    """Traverse structured JSON; only count public post-shaped records."""
    records={};queue=[data];seen=0
    while queue and seen<200000:
        cur=queue.pop();seen+=1
        if isinstance(cur,dict):
            item=cur.get("post") if isinstance(cur.get("post"),dict) else cur
            if isinstance(item,dict) and isinstance(item.get("code"),str):
                code=item["code"]
                if 4<=len(code)<=24 and re.fullmatch(r"[A-Za-z0-9_-]+",code):
                    records[code]=item
            queue.extend(cur.values())
        elif isinstance(cur,list):queue.extend(cur)
    return records

def threads(kind,word,style):
    url="https://www.threads.com/search?"+urllib.parse.urlencode({"q":word,"serp_type":style})
    code,body,error=fetch(url)
    out={"method":"threads_public_embedded_json","word":kind,"style":style,
         "http":code,"bytes":len(body),"error":error}
    if not body:return out
    parser=Scripts()
    try:parser.feed(body)
    except Exception:pass
    out["json_script_blocks"]=len(parser.scripts)
    out["has_thread_items"]=("thread_items" in body)
    out["has_searchResults"]=("searchResults" in body)
    posts={}
    for script in parser.scripts[:35]:
        try:obj=json.loads(script)
        except Exception:continue
        posts.update(collect_posts(obj))
    now=datetime.now(timezone.utc).timestamp()
    out["structured_posts"]=len(posts)
    out["exact_keyword_text"]=0
    out["with_source_date"]=0
    out["posted_last_30_days"]=0
    out["with_media"]=0
    for post in posts.values():
        text=str(post.get("caption",{}).get("text","")) if isinstance(post.get("caption"),dict) else ""
        out["exact_keyword_text"]+=int(word in text)
        try:stamp=float(post.get("taken_at"))
        except (ValueError,TypeError):continue
        if 1100000000<=stamp<=now+86400:
            out["with_source_date"]+=1
            out["posted_last_30_days"]+=int(stamp>=now-30*86400)
        out["with_media"]+=int(bool(post.get("image_versions2") or post.get("carousel_media") or post.get("video_versions")))
    return out

def rsshub(kind,word):
    url="https://rsshub.app/threads/search/"+urllib.parse.quote(word,safe="")+"?serpType=recent"
    status,body,error=fetch(url,"application/rss+xml, text/xml, application/atom+xml")
    out={"method":"rsshub_threads_search","word":kind,"http":status,"bytes":len(body),"error":error}
    if not body:return out
    try:
        root=ET.fromstring(body)
        entries=list(root.findall(".//item"))
        if not entries: entries=list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
        out["feed_items"]=len(entries)
        out["items_with_pubDate"]=sum(bool(x.findtext("pubDate") or x.findtext("{http://www.w3.org/2005/Atom}updated")) for x in entries)
        out["item_text_keyword"]=sum(word in ET.tostring(x,encoding="unicode") for x in entries)
    except ET.ParseError:out["invalid_xml"]=True
    return out

def pixelfed(word):
    url="https://pixelfed.social/api/v1/timelines/tag/"+urllib.parse.quote(word,safe="")+"?limit=5"
    status,body,error=fetch(url,"application/json")
    out={"method":"pixelfed_public_hashtag","word":"control" if word=="커피" else "project",
         "http":status,"error":error}
    try:
        data=json.loads(body);items=data if isinstance(data,list) else []
        out["public_records"]=sum(isinstance(x,dict) and x.get("visibility")=="public" for x in items)
        out["dated_records"]=sum(bool(x.get("created_at")) for x in items if isinstance(x,dict))
    except (ValueError,TypeError):out["valid_json"]=False
    return out

TASKS=[
    (threads,("control",QUERIES["control"],"recent")),
    (threads,("project",QUERIES["project"],"recent")),
    (threads,("control",QUERIES["control"],"tags")),
    (threads,("project",QUERIES["project"],"tags")),
    (rsshub,("control",QUERIES["control"])),
    (rsshub,("project",QUERIES["project"])),
    (pixelfed,(QUERIES["control"],)),
    (pixelfed,(QUERIES["project"],))
]
if __name__=="__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(fn,*args) for fn,args in TASKS]
        for f in futures:
            try:result=f.result()
            except Exception as e:result={"error":type(e).__name__}
            print(json.dumps(result,ensure_ascii=False),flush=True)
