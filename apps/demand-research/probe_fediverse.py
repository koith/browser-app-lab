"""Probe public Fediverse APIs and report aggregate matched post counts only.

Privacy: never output raw posts, author names, profile URLs, or media bytes.
"""
import concurrent.futures, datetime, json, re, urllib.parse, urllib.request
from html import unescape

TERMS=("뒷계","섹트","일탈계")
INSTANCES=("misskey.io","hoto.moe","misskey.design","kmy.blue","nijimiss.moe","misskey.art","misskey.flowers")
CUTOFF=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=30)

def count_matches(data,term,field):
    items=data if isinstance(data,list) else data.get(field,[])
    if not isinstance(items,list):return (0,0,0)
    matched=0;recent=0
    for item in items:
        if not isinstance(item,dict):continue
        text=(item.get("text") or item.get("cw") or "")
        if term not in str(text):continue
        matched+=1
        try:
            when=datetime.datetime.fromisoformat(str(item.get("createdAt") or item.get("created_at") or item.get("published") or "").replace("Z","+00:00"))
            if when>=CUTOFF:recent+=1
        except (ValueError,TypeError):pass
    return len(items),matched,recent

def run(host,term):
    url="https://"+host+"/api/notes/search"
    body=json.dumps({"query":term,"limit":40,"offset":0}).encode("utf-8")
    req=urllib.request.Request(url,data=body,headers={"User-Agent":"Intersection/1.0 (public-readonly-probe)","Accept":"application/json","Content-Type":"application/json","Origin":"https://koith.github.io"})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:
            data=json.load(response)
            n,matched,recent=count_matches(data,term,"notes")
            return {"site":host,"term":term,"http":response.status,"rows":n,"exact":matched,"last_30_days":recent,"cors":response.headers.get("Access-Control-Allow-Origin")}
    except Exception as error:
        return {"site":host,"term":term,"error":str(error)[:95]}

with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
    for item in pool.map(lambda args:run(*args),[(host,term) for host in INSTANCES for term in TERMS]):
        print(json.dumps(item,ensure_ascii=False))
