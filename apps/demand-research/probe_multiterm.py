"""Compare multi-term cross-social free search recall to one-term source queries; counts only."""
import concurrent.futures,json,re,urllib.request,urllib.parse,urllib.error
TERMS=("뒷계","섹트","일탈계")
NETWORKS={"x":(["x.com","twitter.com"],r"^/[A-Za-z0-9_]{1,15}/status/\d+"),
          "threads":(["threads.com","threads.net"],r"^/@[\w.]+/post/[\w-]+"),
          "instagram":(["instagram.com"],r"^/(p|reel)/[\w-]+")}
def valid(platform,u):
    try:
        p=urllib.parse.urlsplit(u)
        return p.scheme=="https" and (p.hostname or "").removeprefix("www.") in NETWORKS[platform][0] and re.match(NETWORKS[platform][1],p.path)
    except:return False
def run(engine,platform,variant):
    domain=NETWORKS[platform][0][0]
    query= 'site:'+domain+' ('+' OR '.join('"'+x+'"' for x in TERMS)+')'
    if variant=="single":query='site:'+domain+' "일탈계"'
    if variant=="hashtags":query='site:'+domain+' ('+' OR '.join('#'+x for x in TERMS)+')'
    data={"query":query,"max_results":35} if engine=="keenable" else {"query":query,"sources":["web"],"limit":20}
    head={"Content-Type":"application/json","User-Agent":"IntersectionMultiQuery/1.0"}
    if engine=="keenable":head["X-Keenable-Title"]="intersection-research"
    url="https://api.keenable.ai/v1/search/public" if engine=="keenable" else "https://api.firecrawl.dev/v2/search"
    req=urllib.request.Request(url,data=json.dumps(data,ensure_ascii=False).encode(),method="POST",headers=head)
    result={"provider":engine,"platform":platform,"variant":variant}
    try:
        with urllib.request.urlopen(req,timeout=23) as res:
            raw=json.load(res)
            rows=raw.get("results",[]) if engine=="keenable" else raw.get("data",{}).get("web",[])
            rows=rows if isinstance(rows,list) else []
            approved=[r for r in rows if isinstance(r,dict) and valid(platform,r.get("url",""))]
            matches=sum(any(term in str(r.get("title",""))+" "+str(r.get("description",""))+" "+str(r.get("snippet","")) for term in TERMS) for r in approved)
            unique=len({urllib.parse.urlsplit(r["url"]).path for r in approved})
            result.update(http=res.status,total=len(rows),canonical=len(approved),unique=unique,snippet_match=matches)
    except urllib.error.HTTPError as e:result.update(http=e.code)
    except Exception as e:result.update(http=0,error=type(e).__name__)
    return result
if __name__=="__main__":
    cases=[(e,p,v) for e in ("keenable","firecrawl") for p in NETWORKS for v in ("or","hashtags")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as x:
        for r in x.map(lambda a:run(*a),cases):print(json.dumps(r,ensure_ascii=False),flush=True)
