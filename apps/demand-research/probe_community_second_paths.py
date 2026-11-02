"""Independent second-path checks after developer community findings.

No login credentials, no session, no changing platform security settings. Public
read-only requests, 9 bounded checks, aggregate diagnostics only. No post text,
IDs, individual usernames, image URLs or direct author identifiers are printed.
"""
from __future__ import annotations
from html.parser import HTMLParser
import concurrent.futures,json,re,urllib.parse,urllib.request,urllib.error
UA="IntersectionPublicSourceEvaluation/1.0"
class JsonScripts(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.parts=[];self.scripts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="script" and a.get("type")=="application/json":
            self.active=True;self.parts=[]
    def handle_data(self,t):
        if self.active:self.parts.append(t)
    def handle_endtag(self,tag):
        if tag=="script" and self.active:
            self.scripts.append("".join(self.parts));self.parts=[];self.active=False
def get(url,cap=1500000):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={
          "User-Agent":UA,"Accept":"application/json, text/html"}),timeout=14) as r:
            return r.status,r.read(cap).decode("utf-8","replace"),""
    except urllib.error.HTTPError as e:
        return e.code,"","HTTP denied"
    except Exception as e:return 0,"",type(e).__name__
def instagram_html():
    status,body,error=get("https://www.instagram.com/nasa/",cap=1900000)
    out={"source":"instagram_anon_html_json","http":status,"error":error,"bytes":len(body)}
    parser=JsonScripts()
    try:parser.feed(body)
    except Exception:pass
    out["json_blocks"]=len(parser.scripts)
    postkeys=set();timekeys=set();userNodeCount=0;nodes=0
    for raw in parser.scripts[:110]:
        try:obj=json.loads(raw)
        except Exception:continue
        todo=[obj]
        while todo and nodes<300000:
            x=todo.pop();nodes+=1
            if isinstance(x,list):todo.extend(x)
            elif isinstance(x,dict):
                if "xig_user_by_username" in x:userNodeCount+=1
                if isinstance(x.get("shortcode"),str):
                    postkeys.add(x["shortcode"])
                    if x.get("taken_at") or x.get("taken_at_timestamp"):timekeys.add(x["shortcode"])
                todo.extend(x.values())
    out.update(user_info_nodes=userNodeCount,
       canonical_post_records=len(postkeys),dated_post_records=len(timekeys))
    out["has_profile_id"]=bool(re.search(r'"profile_id":"\d+"',body))
    out["has_public_graphql_tokens"]=bool(re.search(r'"LSD",\[\],\{"token":',body))
    return out
def bluesky(endpoint,term):
    url=endpoint+"/xrpc/app.bsky.feed.searchPosts?"+urllib.parse.urlencode({"q":term,"limit":70,"sort":"latest"})
    code,body,error=get(url,cap=2600000)
    result={"source":"bluesky_crosspost_refs","endpoint":"api" if endpoint=="https://api.bsky.app" else "pds",
            "http":code,"error":error}
    try:
        rows=json.loads(body).get("posts",[])
        found={"x":0,"threads":0,"instagram":0}
        pattern=re.compile(r"https?://(?:www\.)?(x\.com|twitter\.com|threads\.(?:com|net)|instagram\.com)/[^\s<>\"']+",re.I)
        for post in rows if isinstance(rows,list) else []:
            record=post.get("record") or {}
            links=pattern.findall(str(record.get("text") or ""))
            embed=post.get("embed") or {}
            if isinstance(embed,dict):
                uri=(embed.get("external") or {}).get("uri")
                if uri:links.extend(pattern.findall(str(uri)))
            for feature in record.get("facets",[]) or []:
                for part in feature.get("features",[]) or []:
                    if part.get("uri"):links.extend(pattern.findall(str(part["uri"])))
            kinds=set("x" if t in ("x.com","twitter.com") else
                "threads" if t.startswith("threads.") else "instagram" for t in links)
            for k in kinds:found[k]+=1
        result.update(posts=len(rows),crosspost_links=sum(found.values()),
                      x_links=found["x"],threads_links=found["threads"],instagram_links=found["instagram"])
    except Exception:result["parsed"]=False
    return result
def arctic(mode):
    base="https://arctic-shift.photon-reddit.com/api/posts/search?"
    params={"limit":3,"sort":"desc","fields":"id,created_utc,title,subreddit"}
    if mode=="scoped":
        params.update({"subreddit":"Coffee","title":"coffee","after":"2026-10-25"})
    elif mode=="topic":
        params.update({"subreddit":"korea","query":"일탈계"})
    else:
        params.update({"subreddit":"Coffee"})
    http,body,error=get(base+urllib.parse.urlencode(params))
    out={"source":"arctic_scoped_keyword","mode":mode,"http":http,"error":error}
    try:
        data=json.loads(body)
        rows=data.get("data",[]) if isinstance(data,dict) else []
        out["records"]=len(rows)
        out["dated_records"]=sum(bool(x.get("created_utc")) for x in rows if isinstance(x,dict))
    except Exception:out["parsed"]=False
    return out
TASKS=[(instagram_html,()),(bluesky,("https://api.bsky.app","섹트")),
       (bluesky,("https://bsky.social","섹트")),
       (arctic,("scoped",)),(arctic,("topic",)),(arctic,("feed",))]
if __name__=="__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for item in ex.map(lambda t:t[0](*t[1]),TASKS):
            print(json.dumps(item,ensure_ascii=False),flush=True)
