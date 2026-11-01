"""Zero-cost public-index feasibility check (no keys, no proxy evasion).

Only print aggregate diagnostics. Never save source URLs, usernames, text, or images.
Each service is queried at most a few times. HTTP errors are terminal.
This does not establish permission to republish or archive source content.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, parse_qs, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import re
import xml.etree.ElementTree as ET

TERM="일탈계"
TARGETS={
    "x":("x.com","twitter.com"),
    "threads":("threads.com","threads.net"),
    "instagram":("instagram.com",),
}
PATTERNS={
    "x":re.compile(r"^/[^/]+/status/[0-9]+(?:/|$)"),
    "threads":re.compile(r"^/@[^/]+/post/[^/?#]+"),
    "instagram":re.compile(r"^/(?:p|reel)/[^/?#]+"),
}

def canonical(link, platform):
    """Count only canonical public post URLs; ignore profile/search/home links."""
    try:
        u=urlsplit(link.strip())
        host=(u.hostname or "").lower().removeprefix("www.")
        if u.scheme not in ("http","https") or host not in TARGETS[platform]:
            return False
        return bool(PATTERNS[platform].match(u.path))
    except Exception:
        return False

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        opts=dict(attrs)
        if "href" not in opts:
            return
        link=opts["href"]
        if link.startswith("//"):
            link="https:"+link
        if link.startswith("/l/?"):
            link=parse_qs(urlsplit(link).query).get("uddg",[""])[0]
        self.links.append(unquote(link))

def get(url, accept):
    req=Request(url,headers={"User-Agent":"IntersectionZeroCostResearch/1.0 (public metadata check)","Accept":accept})
    with urlopen(req,timeout=13) as response:
        return response.status,response.read(400000)

def bing(platform):
    domain=TARGETS[platform][0]
    query='site:'+domain+' "'+TERM+'"'
    url="https://www.bing.com/search?"+urlencode({"q":query,"format":"rss"})
    status,data=get(url,"application/rss+xml, application/xml")
    root=ET.fromstring(data)
    links=[str(node.text or "") for node in root.findall(".//item/link")]
    matched=sum(canonical(x,platform) for x in links)
    return {"source":"bing_rss","platform":platform,"http":status,"items":len(links),"canonical_posts":matched}

def duckduckgo(platform):
    domain=TARGETS[platform][0]
    query='site:'+domain+' "'+TERM+'"'
    url="https://html.duckduckgo.com/html/?"+urlencode({"q":query})
    status,data=get(url,"text/html")
    parser=LinkParser()
    parser.feed(data.decode("utf-8","replace"))
    links=set(parser.links)
    matched=sum(canonical(x,platform) for x in links)
    return {"source":"ddg_html","platform":platform,"http":status,"unique_links":len(links),"canonical_posts":matched}

def pullpush():
    url="https://api.pullpush.io/reddit/search/submission/?"+urlencode({"q":TERM,"size":15,"sort":"desc"})
    status,data=get(url,"application/json")
    obj=json.loads(data)
    entries=obj.get("data",[]) if isinstance(obj,dict) else []
    valid=sum(bool(isinstance(x,dict) and (x.get("permalink") or x.get("id"))) for x in entries)
    return {"source":"pullpush","platform":"reddit","http":status,"items":len(entries),"valid_records":valid}

def arctic(term):
    url="https://arctic-shift.photon-reddit.com/api/posts/search?"+urlencode({"query":term,"limit":5,"sort":"desc"})
    status,data=get(url,"application/json")
    obj=json.loads(data)
    entries=obj.get("data",[]) if isinstance(obj,dict) else []
    valid=sum(bool(isinstance(x,dict) and x.get("id") and x.get("created_utc")) for x in entries)
    return {"source":"arctic_shift","platform":"reddit","query":"project" if term==TERM else "control","http":status,"items":len(entries),"valid_records":valid}

def run(fn,platform):
    try:
        return fn(platform) if platform else fn()
    except HTTPError as e:
        return {"source":fn.__name__,"platform":platform or "reddit","http":e.code,"error":"HTTP denied"}
    except Exception as e:
        return {"source":fn.__name__,"platform":platform or "reddit","error":type(e).__name__,"message":str(e)[:75]}

def main():
    tasks=[(bing,p) for p in TARGETS]+[(duckduckgo,p) for p in TARGETS]+[(pullpush,None),(arctic,TERM),(arctic,"coffee")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(lambda v:run(*v),tasks):
            print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
