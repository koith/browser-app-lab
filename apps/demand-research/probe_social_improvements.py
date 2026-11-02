"""Zero-cost SNS cross-source feasibility, aggregate-only. No user posts are stored or logged.
Probe keyless time-aware search, Meta tokenless oEmbed and Keenable public fetch.
"""
import concurrent.futures,json,re,urllib.parse,urllib.request,urllib.error
from datetime import datetime,timezone,timedelta
UA="IntersectionFreeSocialR&D/1.0"
CASES=[("x","x.com","섹트"),("threads","threads.com","일탈계"),("instagram","instagram.com","뒷계")]
PAT={"x":re.compile(r"^/[A-Za-z0-9_]{1,15}/status/[0-9]+"),"threads":re.compile(r"^/@[A-Za-z0-9._]+/post/[A-Za-z0-9_-]+"),"instagram":re.compile(r"^/(?:p|reel)/[A-Za-z0-9_-]+")}
HOST={"x":("x.com","twitter.com"),"threads":("threads.com","threads.net"),"instagram":("instagram.com",)}
def http(url,body=None,headers=None,timeout=22):
    hdr={"User-Agent":UA,"Accept":"application/json"}
    hdr.update(headers or {})
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    if data:hdr["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,headers=hdr,method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return r.status,json.loads(r.read(650000))
    except urllib.error.HTTPError as e:return e.code,{}
    except Exception:return 0,{}
def normalized(row,p):
    if not isinstance(row,dict):return None
    try:
        u=urllib.parse.urlsplit(str(row.get("url") or ""))
        if u.scheme!="https" or (u.hostname or "").removeprefix("www.") not in HOST[p] or not PAT[p].match(u.path):return None
        return urllib.parse.urlunsplit(("https",u.hostname,u.path,"",""))
    except (ValueError,TypeError):return None
def search(engine,p,domain,term,date):
    query='site:'+domain+' "'+term+'"'
    data=({"query":query,"limit":20,"sources":["web"],"tbs":"qdr:m"} if engine=="firecrawl" and date else
          {"query":query,"limit":20,"sources":["web"]} if engine=="firecrawl" else
          {"query":query+(" after:2026-10-01" if date else ""),"max_results":30})
    headers={"X-Keenable-Title":"intersection-research"} if engine=="keenable" else {}
    url="https://api.firecrawl.dev/v2/search" if engine=="firecrawl" else "https://api.keenable.ai/v1/search/public"
    code,payload=http(url,data,headers)
    rows=payload.get("data",{}).get("web",[]) if engine=="firecrawl" else payload.get("results",[])
    if not isinstance(rows,list):rows=[]
    good=[(normalized(x,p),term in str(x.get("title",""))+" "+str(x.get("description",""))+" "+str(x.get("snippet",""))) for x in rows if isinstance(x,dict)]
    good=[x for x in good if x[0]]
    return {"type":"search","provider":engine,"platform":p,"time_filter":date,"http":code,
            "result_count":len(rows),"canonical":len(good),"keyword_snippet":sum(x[1] for x in good),
            "url":next((x[0] for x in good if x[1]),None)}
def oembed(url,p):
    if not url:return {"type":"oembed","platform":p,"http":0,"missing_candidate":True}
    paths={"threads":["https://graph.threads.com/oembed","https://graph.facebook.com/v25.0/threads_oembed"],
           "instagram":["https://graph.facebook.com/v25.0/instagram_oembed"]}
    out=[]
    for base in paths[p]:
        code,data=http(base+"?"+urllib.parse.urlencode({"url":url,"omitscript":"true"}))
        text=str(data.get("html") or "")
        out.append({"endpoint":"graph_threads" if "threads.com/oembed" in base else "graph_facebook",
                    "http":code,"html_available":bool(text),"html_mentions_keyword":("일탈계" if p=="threads" else "뒷계") in text,
                    "has_timestamp":bool(re.search(r"datetime=|<time|published",text,re.I)),
                    "author_known":bool(data.get("author_name"))})
        if code==200:break
    return {"type":"oembed","platform":p,"responses":out}
def keenable_fetch(url,p):
    if not url:return {"type":"keenable_fetch","platform":p,"http":0,"no_candidate":True}
    code,data=http("https://api.keenable.ai/v1/fetch/public?"+urllib.parse.urlencode({"url":url}),
                   headers={"X-Keenable-Title":"intersection-research"})
    output={"type":"keenable_fetch","platform":p,"http":code}
    for k in ("content","markdown","text"):
        if isinstance(data.get(k),str):
            output["content_available"]=bool(data[k].strip())
            output["exact_term"]=("일탈계" if p=="threads" else "뒷계") in data[k]
            break
    return output
def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        tasks=[(engine,*row,when) for engine in ("firecrawl","keenable") for row in CASES for when in (False,True)]
        results=list(pool.map(lambda a:search(*a),tasks))
    for x in results:
        print(json.dumps({k:v for k,v in x.items() if k!="url"},ensure_ascii=False),flush=True)
    for p in ("threads","instagram"):
        candidates=[x["url"] for x in results if x["platform"]==p and x.get("url")]
        url=candidates[0] if candidates else None
        print(json.dumps(oembed(url,p),ensure_ascii=False),flush=True)
        print(json.dumps(keenable_fetch(url,p),ensure_ascii=False),flush=True)
if __name__=="__main__":main()
