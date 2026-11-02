"""Keyless public search comparison: Firecrawl vs Keenable.

No account, API key, cookies, payments, media or archived posts.
Only publish aggregate counts; canonical social post URLs are checked in memory.
Limited to eight public search calls to avoid shared quota abuse.
"""
import concurrent.futures, json, re, urllib.error, urllib.parse, urllib.request
SITES={"x":["x.com","twitter.com"],"threads":["threads.com","threads.net"],"instagram":["instagram.com"]}
PATHS={"x":re.compile(r"^/[^/]+/status/[0-9]+(?:/|$)"),"threads":re.compile(r"^/@[^/]+/post/[A-Za-z0-9_-]+(?:/|$)"),
       "instagram":re.compile(r"^/(?:p|reel)/[A-Za-z0-9_-]+(?:/|$)")}
TESTS=[("x","섹트"),("threads","일탈계"),("instagram","뒷계"),("x","coffee")]
SOURCES={"firecrawl":"https://api.firecrawl.dev/v2/search","keenable":"https://api.keenable.ai/v1/search/public"}

def count_valid(platform,items):
    n=0;host_n=0;term_n=0
    for r in items:
        if not isinstance(r,dict):continue
        try:
            p=urllib.parse.urlsplit(str(r.get("url","")))
            host=(p.hostname or "").lower().removeprefix("www.")
            if p.scheme not in ("https","http") or host not in SITES[platform]:continue
            host_n+=1
            if PATHS[platform].match(p.path):n+=1
        except (ValueError,TypeError):pass
    return n,host_n

def probe(engine,platform,term):
    result={"provider":engine,"network":platform,"term":"control" if term=="coffee" else "project"}
    domain=SITES[platform][0]
    body={"query":'site:'+domain+' "'+term+'"',"limit":10}
    headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"IntersectionFreeSourceBenchmark/1.0"}
    if engine=="firecrawl":
        body["sources"]=["web"]
    else:
        body={"query":body["query"],"max_results":10}
        headers["X-Keenable-Title"]="intersection-research"
    req=urllib.request.Request(SOURCES[engine],data=json.dumps(body,ensure_ascii=False).encode(),method="POST",headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=23) as response:
            data=json.loads(response.read(450000))
            items=(data.get("data",{}).get("web",[]) if engine=="firecrawl" else data.get("results",[]))
            if not isinstance(items,list):items=[]
            valid,host=count_valid(platform,items)
            result.update(http=response.status,results=len(items),source_domains=host,canonical_posts=valid,
                          successful_payload=bool(data.get("success",True)) if isinstance(data,dict) else False)
            if engine=="firecrawl":
                result["credits_used"]=data.get("creditsUsed") if isinstance(data.get("creditsUsed"),int) else None
    except urllib.error.HTTPError as e:
        result.update(http=e.code,error="Provider HTTP denial")
    except Exception as e:
        result.update(http=0,error=type(e).__name__)
    return result

if __name__=="__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for row in pool.map(lambda args:probe(*args),[(e,*t) for e in SOURCES for t in TESTS]):
            print(json.dumps(row,ensure_ascii=False),flush=True)
