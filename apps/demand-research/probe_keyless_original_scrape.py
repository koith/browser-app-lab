"""Bounded zero-key search->scrape verification for public indexed SNS URLs.

No login/private access or bypass, no URL/person/media/text saved or printed.
At most 3 Firecrawl Search calls and 3 Firecrawl Scrape calls, once per
network (X, Threads, Instagram). These scans test content verification
feasibility, not permission to archive or claim comprehensive collection.
"""
import json,re,urllib.parse,urllib.request,urllib.error,datetime

CASES=[("x","x.com","섹트",r"^/[A-Za-z0-9_]{1,15}/status/\d+(?:/|$)"),
("threads","threads.com","일탈계",r"^/@[A-Za-z0-9._]+/post/[A-Za-z0-9_-]+(?:/|$)"),
("instagram","instagram.com","뒷계",r"^/(?:p|reel)/[A-Za-z0-9_-]+(?:/|$)")]
UA="IntersectionOriginalProof/1.0"

def req(path,payload):
    data=json.dumps(payload,ensure_ascii=False).encode()
    q=urllib.request.Request("https://api.firecrawl.dev/v2/"+path,data=data,
        method="POST",headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":UA})
    try:
        with urllib.request.urlopen(q,timeout=25) as res:
            return res.status,json.loads(res.read(1250000))
    except urllib.error.HTTPError as e:return e.code,{}
    except Exception:return 0,{}

def check(platform,domain,term,pattern):
    r={"source":"firecrawl_search_scrape","platform":platform,"term":"project"}
    code,payload=req("search",{"query":'site:'+domain+' "'+term+'"',"limit":10,"sources":["web"]})
    r["search_http"]=code
    rows=payload.get("data",{}).get("web",[]) if isinstance(payload,dict) else []
    selected=None
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):continue
        try:
            url=urllib.parse.urlsplit(row.get("url",""))
            host=(url.hostname or "").lower().removeprefix("www.")
            if url.scheme!="https" or host not in (domain, "threads.net" if platform=="threads" else "twitter.com" if platform=="x" else domain):continue
            if not re.match(pattern,url.path):continue
            if term not in str(row.get("title",""))+" "+str(row.get("description","")):continue
            selected=urllib.parse.urlunsplit(("https",host,url.path,"",""))
            break
        except Exception:continue
    r["found_canonical_with_matching_snippet"]=bool(selected)
    if not selected:
        return r
    http,data=req("scrape",{"url":selected,"formats":["markdown"],"onlyMainContent":True,"timeout":18000})
    r["scrape_http"]=http
    r["scrape_success"]=data.get("success") is True
    obj=data.get("data",{}) if isinstance(data.get("data"),dict) else {}
    markdown=str(obj.get("markdown") or "")
    meta=obj.get("metadata",{}) if isinstance(obj.get("metadata"),dict) else {}
    r["markdown_nonempty"]=bool(markdown.strip())
    r["keyword_in_page"]=term in markdown
    r["metadata_date_present"]=bool(meta.get("publishedTime") or meta.get("article:published_time") or meta.get("publishedDate"))
    r["page_status"]=meta.get("statusCode") if isinstance(meta.get("statusCode"),int) else None
    return r

if __name__=="__main__":
    for row in CASES:
        print(json.dumps(check(*row),ensure_ascii=False),flush=True)
