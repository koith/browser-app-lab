"""Check public no-key original text for Threads/Instagram links, without logging URLs/text."""
import json,re,urllib.request,urllib.parse,urllib.error,concurrent.futures
UA="IntersectionFreeOriginalProbe/1.0"
PLATFORMS={"threads":("threads.com","일탈계",r"^/@[a-zA-Z0-9._]+/post/[\w-]+"),
           "instagram":("instagram.com","뒷계",r"^/(p|reel)/[\w-]+")}
def req(url,data=None,h=None,method=None):
    headers={"User-Agent":UA,"Accept":"application/json"}
    headers.update(h or {})
    encoded=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
    if encoded:headers["Content-Type"]="application/json"
    request=urllib.request.Request(url,data=encoded,method=method or ("POST" if data is not None else "GET"),headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=17) as res:
            raw=res.read(600000)
            try: val=json.loads(raw)
            except:val={}
            return res.status,val,dict(res.headers)
    except urllib.error.HTTPError as e:return e.code,{},dict(e.headers)
    except Exception:return 0,{},{}
def eligible(url,platform):
    try:
        p=urllib.parse.urlsplit(url)
        return (p.scheme=="https" and
                (p.hostname or "").removeprefix("www.") in
                  ((PLATFORMS[platform][0], "threads.net") if platform=="threads" else (PLATFORMS[platform][0],))
                and re.match(PLATFORMS[platform][2],p.path))
    except Exception:return False
def run(platform):
    domain,term,_=PLATFORMS[platform]
    q='site:'+domain+' "'+term+'"'
    status,data,_=req("https://api.keenable.ai/v1/search/public",
                 {"query":q,"max_results":25},{"X-Keenable-Title":"intersection-research"})
    rows=data.get("results",[])
    links=[]
    for r in rows if isinstance(rows,list) else []:
        if isinstance(r,dict) and eligible(str(r.get("url","")),platform):
            if r["url"] not in links:links.append(r["url"])
    print(json.dumps({"platform":platform,"stage":"discovery","http":status,"candidates":len(links)}),flush=True)
    for i,url in enumerate(links[:4]):
        code,payload,headers=req("https://api.keenable.ai/v1/fetch/public?"+
                            urllib.parse.urlencode({"url":url}),h={"X-Keenable-Title":"intersection-research"})
        keys=list(payload)[:20] if isinstance(payload,dict) else []
        content=str(payload.get("content") or payload.get("markdown") or payload.get("text") or "")
        serialized=json.dumps(payload,ensure_ascii=False)
        print(json.dumps({"platform":platform,"stage":"fetch","index":i,"http":code,
            "keys":keys,"chars":len(content),"keyword_in_text":term in content,
            "date_patterns":len(re.findall(r"202[456][-/年.][0-1]?\d",content)),
            "time_tag":bool(re.search(r"datetime=|created_at|published_at|<time",content,re.I)),
            "metadata_object":isinstance(payload.get("metadata"),dict)},ensure_ascii=False),flush=True)
        if platform=="threads":
            endpoints=["https://graph.threads.com/oembed","https://graph.facebook.com/v25.0/threads_oembed"]
        else:endpoints=["https://graph.facebook.com/v25.0/instagram_oembed"]
        for ep in endpoints:
            c,d,h=req(ep+"?"+urllib.parse.urlencode({"url":url}))
            html=str(d.get("html") or "")
            print(json.dumps({"platform":platform,"stage":"oembed","index":i,
                "http":c,"html":len(html),"keyword":term in html,"date":bool(re.search(r"datetime=|<time|202[456]",html,re.I)),
                "type":str(d.get("type") or "")},ensure_ascii=False),flush=True)
            if c==200:break
    cors_headers={"Origin":"https://koith.github.io","Access-Control-Request-Method":"GET",
                  "Access-Control-Request-Headers":"x-keenable-title"}
    c,_,h=req("https://api.keenable.ai/v1/fetch/public",method="OPTIONS",h=cors_headers)
    print(json.dumps({"platform":platform,"stage":"cors","http":c,
        "allow_origin":h.get("Access-Control-Allow-Origin") in ("*","https://koith.github.io"),
        "allow_headers":"x-keenable-title" in str(h.get("Access-Control-Allow-Headers","")).lower()},ensure_ascii=False),flush=True)
def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:
        list(p.map(run,PLATFORMS))
if __name__=="__main__":main()
