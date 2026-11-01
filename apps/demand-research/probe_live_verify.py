"""Private-in-process verification of keyless search results, never archive any post.

Counts exact-term snippets, canonical URLs, duplicates, HTML/CORS exposure.
Uses bounded follow-up on *public* X statuses only (max 5) to validate that
an indexed candidate resolves to the actual platform record. No raw content,
usernames, URLs, media or identifiers are printed or saved.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import json,re,urllib.parse,urllib.request,urllib.error

CASES=(("x","섹트"),("threads","일탈계"),("instagram","뒷계"))
HOSTS={"x":("x.com","twitter.com"),"threads":("threads.net","threads.com"),"instagram":("instagram.com",)}
PATTERNS={"x":re.compile(r"^/[^/]+/status/(\d+)(?:/|$)"),"threads":re.compile(r"^/@[^/]+/post/([A-Za-z0-9_-]+)(?:/|$)"),"instagram":re.compile(r"^/(?:p|reel)/([A-Za-z0-9_-]+)(?:/|$)")}
APIS={"firecrawl":"https://api.firecrawl.dev/v2/search","keenable":"https://api.keenable.ai/v1/search/public"}
UA="IntersectionPublicSourceVerification/1.0"

def request(url,data=None,headers=None,timeout=18,method=None):
    h={"User-Agent":UA,"Accept":"application/json"}
    h.update(headers or {})
    encoded=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
    if encoded:h["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=encoded,headers=h,method=method or ("POST" if data is not None else "GET"))
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return r.status,r.read(450000),dict(r.headers)
    except urllib.error.HTTPError as e:return e.code,b"",dict(e.headers)
    except Exception:return 0,b"",{}

def canonical(platform,url):
    try:
        p=urllib.parse.urlsplit(url)
        host=(p.hostname or "").lower().removeprefix("www.")
        if p.scheme not in ("http","https") or host not in HOSTS[platform]:return None
        m=PATTERNS[platform].match(p.path)
        if not m:return None
        return (host,p.path.rstrip("/"),m.group(1))
    except (ValueError,TypeError):return None

def search(engine,platform,term):
    q='site:'+HOSTS[platform][0]+' "'+term+'"'
    payload={"query":q,"limit":10,"sources":["web"]} if engine=="firecrawl" else {"query":q,"max_results":10}
    hdr={"X-Keenable-Title":"intersection-research"} if engine=="keenable" else {}
    status,raw,_=request(APIS[engine],payload,hdr,timeout=25)
    if status!=200:return status,[],[]
    try:
        d=json.loads(raw)
        rows=d.get("data",{}).get("web",[]) if engine=="firecrawl" else d.get("results",[])
    except (ValueError,AttributeError):return status,[],[]
    valid=[]
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):continue
        src=str(row.get("url") or "")
        parsed=canonical(platform,src)
        if parsed:
            summary=" ".join(str(row.get(k) or "") for k in ("title","description","snippet","highlight"))
            valid.append((parsed,term in summary))
    return status,valid,rows if isinstance(rows,list) else []

def cors(engine):
    headers={"Origin":"https://koith.github.io","Access-Control-Request-Method":"POST",
        "Access-Control-Request-Headers":"content-type, x-keenable-title" if engine=="keenable" else "content-type"}
    status,_,h=request(APIS[engine],headers=headers,method="OPTIONS",timeout=12)
    allowance=h.get("Access-Control-Allow-Origin") or h.get("access-control-allow-origin","")
    return {"provider":engine,"http":status,"browser_origin_allowed":allowance in ("*","https://koith.github.io"),
            "allowed_methods":(h.get("Access-Control-Allow-Methods","") or "").lower().find("post")>=0}

def x_check(status_id,term):
    code,raw,_=request("https://api.fxtwitter.com/status/"+status_id,timeout=10)
    if code!=200:return {"http":code,"real":False,"match":False,"recent":False}
    try:
        post=json.loads(raw).get("tweet",{})
        text=str(post.get("text") or "")
        dt=str(post.get("created_at") or "")
        stamp=datetime.fromisoformat(dt.replace("Z","+00:00"))
        return {"http":code,"real":bool(post.get("id")),"match":term in text,
                "recent":datetime.now(timezone.utc)-timedelta(days=32)<=stamp<=datetime.now(timezone.utc)}
    except (ValueError,TypeError,AttributeError):return {"http":code,"real":False,"match":False,"recent":False}

def main():
    for engine in APIS:
        print(json.dumps({"step":"cors",**cors(engine)}),flush=True)
    for platform,term in CASES:
        a={}
        for engine in APIS:
            code,valid,raw=search(engine,platform,term)
            keys={tuple(p[:2]) for p,m in valid}
            a[engine]=(keys,valid)
            print(json.dumps({"step":"search","engine":engine,"platform":platform,"http":code,
                "index_results":len(raw),"canonical_links":len(valid),
                "snippet_exact_term":sum(m for _,m in valid),"unique_links":len(keys)}),flush=True)
        union=a["firecrawl"][0]|a["keenable"][0]
        overlap=a["firecrawl"][0]&a["keenable"][0]
        print(json.dumps({"step":"dedup","platform":platform,"union":len(union),
                          "overlap":len(overlap)}),flush=True)
        if platform=="x":
            ids=[]
            for _,valid in a.values():
                for p,_ in valid:
                    if p[2] not in ids:ids.append(p[2])
            with ThreadPoolExecutor(max_workers=3) as pool:
                checks=list(pool.map(lambda x:x_check(x,term),ids[:5]))
            print(json.dumps({"step":"live_x","checked":len(checks),"http_200":sum(c["http"]==200 for c in checks),
                "actual_posts":sum(c["real"] for c in checks),
                "exact_keyword":sum(c["match"] for c in checks),
                "posted_last_32_days":sum(c["recent"] for c in checks)}),flush=True)

if __name__=="__main__":main()
