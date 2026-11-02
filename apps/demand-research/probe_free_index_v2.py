"""Compare no-key public indexed search against real canonical post permalink shapes.

Runs a small, bounded matrix. Only aggregate counts leave the process:
no source URLs, usernames, texts, media or page bodies are persisted.
"""
from __future__ import annotations
import concurrent.futures, json, re, urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET

PATTERNS={
"x":re.compile(r"^/[^/]+/status/[0-9]+(?:/|$)"),
"threads":re.compile(r"^/@[^/]+/post/[A-Za-z0-9_-]+(?:/|$)"),
"instagram":re.compile(r"^/(p|reel)/[A-Za-z0-9_-]+(?:/|$)"),
}
HOSTS={"x":{"x.com","twitter.com"},
"threads":{"threads.com","threads.net"},
"instagram":{"instagram.com"}}
MATRIX=[
("x","x.com","섹트"),("x","x.com","일탈계"),("x","twitter.com","뒷계"),("x","twitter.com","coffee"),
("threads","threads.net","섹트"),("threads","threads.com","일탈계"),("threads","threads.com","뒷계"),("threads","threads.net","coffee"),
("instagram","instagram.com/p/","섹트"),("instagram","instagram.com/reel/","일탈계"),("instagram","instagram.com","뒷계"),("instagram","instagram.com","coffee"),
]

def safe_match(platform,link):
    try:
        p=urllib.parse.urlsplit(link)
        host=(p.hostname or "").lower().removeprefix("www.")
        return (p.scheme in ("http","https") and host in HOSTS[platform] and bool(PATTERNS[platform].match(p.path)))
    except (ValueError,TypeError):
        return False

def query(entry):
    platform,domain,word=entry
    q='site:'+domain+' "'+word+'"'
    url="https://www.bing.com/search?"+urllib.parse.urlencode({"q":q,"format":"rss"})
    out={"platform":platform,"scope":domain,"term":"control" if word=="coffee" else str(("섹트","일탈계","뒷계").index(word)+1)}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"IntersectionNoCostIndexProbe/1.0","Accept":"application/rss+xml"})
        with urllib.request.urlopen(req,timeout=10) as response:
            root=ET.fromstring(response.read(300000))
            links=[str(e.text or "") for e in root.findall(".//item/link")]
            out.update(http=response.status,items=len(links),canonical_posts=sum(safe_match(platform,link) for link in links))
            out["source_host_matches"]=sum((urllib.parse.urlsplit(l).hostname or "").lower().removeprefix("www.") in HOSTS[platform] for l in links)
    except urllib.error.HTTPError as e:
        out.update(http=e.code,error="HTTP denied")
    except Exception as e:
        out.update(http=0,error=type(e).__name__)
    return out

if __name__=="__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for item in pool.map(query,MATRIX):
            print(json.dumps(item,ensure_ascii=False),flush=True)
