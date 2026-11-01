"""Bounded aggregate-only survey of free public social-discovery endpoints.

Purpose: prove whether a provider returns real public records from the CI network.
No credentials, media downloads, proxy rotations, content archives, or logged posts.
A success result is not authorization to republish the posts. Never log identifiers.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import html
import time
import xml.etree.ElementTree as ET

TARGET="일탈계"
CONTROL="커피"
UA="IntersectionResearch/1.0 (public API compatibility probe)"
TIMEOUT=9

def request(url, method="GET", body=None, headers=None):
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    h={"User-Agent":UA,"Accept":"application/json, text/html;q=0.8"}
    h.update(headers or {})
    if data: h["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as res:
            return res.status,res.read(400000).decode("utf-8","replace"),None
    except urllib.error.HTTPError as e:
        return e.code,e.read(1000).decode("utf-8","replace"), "HTTP denied"
    except Exception as e:
        return 0,"",type(e).__name__

def probe(kind,query=""):
    result={"source":kind,"query":("control" if query==CONTROL else ("none" if not query else "target:"+str(("일탈계","섹트","뒷계").index(query)+1) if query in ("일탈계","섹트","뒷계") else "other"))}
    if kind=="x_fxtwitter":
        status,body,err=request("https://api.fxtwitter.com/status/20")
        try: count=int(bool(json.loads(body).get("tweet",{}).get("id")))
        except Exception: count=0
    elif kind=="x_vxtwitter":
        status,body,err=request("https://api.vxtwitter.com/Twitter/status/20")
        try: count=int(bool(json.loads(body).get("tweetID")))
        except Exception: count=0
    elif kind=="ig_profile":
        status,body,err=request("https://www.instagram.com/api/v1/users/web_profile_info/?username=nasa",headers={"x-ig-app-id":"936619743392459"})
        try:
            user=json.loads(body).get("data",{}).get("user",{})
            count=int(bool(user.get("id") and not user.get("is_private",True)))
        except Exception: count=0
    elif kind=="telegram_preview":
        status,body,err=request("https://t.me/s/telegram")
        count=len(re.findall(r'data-post="',body))
        result["html_message_elements"]=count
    elif kind=="telegramme":
        status,body,err=request("https://tme.koval-dev.org/v1/body/durov")
        try: count=int(bool(json.loads(body)))
        except Exception: count=0
    elif kind=="opentg":
        url="https://api.opentg.ai/v1/search?"+urllib.parse.urlencode({"q":query,"limit":5})
        status,body,err=request(url)
        try: 
            obj=json.loads(body);count=len(obj.get("results",obj.get("posts",[]))) if isinstance(obj,dict) else 0
        except Exception: count=0
    elif kind=="arctic_scoped":
        url="https://arctic-shift.photon-reddit.com/api/posts/search?"+urllib.parse.urlencode({"subreddit":"Coffee" if query==CONTROL else "korea","query":query,"limit":3,"sort":"desc"})
        status,body,err=request(url)
        try:
            obj=json.loads(body);count=len(obj.get("data",[])) if isinstance(obj,dict) else 0
        except Exception: count=0
    elif kind=="arctic_subreddit":
        url="https://arctic-shift.photon-reddit.com/api/posts/search?"+urllib.parse.urlencode({"subreddit":"programming","limit":3,"sort":"desc"})
        status,body,err=request(url)
        try:
            obj=json.loads(body);count=len(obj.get("data",[])) if isinstance(obj,dict) else 0
        except Exception: count=0
    elif kind=="reddit_public":
        status,body,err=request("https://www.reddit.com/r/programming/new.json?limit=3")
        try: count=len(json.loads(body).get("data",{}).get("children",[]))
        except Exception: count=0
    elif kind=="misskey_m544":
        status,body,err=request("https://misskey.m544.net/api/notes/search","POST",{"query":query,"limit":8})
        try: count=len(json.loads(body)) if isinstance(json.loads(body),list) else 0
        except Exception: count=0
    elif kind=="misskey_sushi":
        status,body,err=request("https://sushi.ski/api/notes/search","POST",{"query":query,"limit":8})
        try: count=len(json.loads(body)) if isinstance(json.loads(body),list) else 0
        except Exception: count=0
    elif kind=="invidious":
        url="https://inv.nadeko.net/api/v1/search?"+urllib.parse.urlencode({"q":query,"type":"video"})
        status,body,err=request(url)
        try: count=len(json.loads(body)) if isinstance(json.loads(body),list) else 0
        except Exception: count=0
    elif kind=="youtube_oembed":
        url="https://www.youtube.com/oembed?"+urllib.parse.urlencode({"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","format":"json"})
        status,body,err=request(url)
        try: count=int(bool(json.loads(body).get("title")))
        except Exception: count=0
    elif kind=="tiktok_oembed":
        url="https://www.tiktok.com/oembed?"+urllib.parse.urlencode({"url":"https://www.tiktok.com/@tiktok/video/7106594312292453675"})
        status,body,err=request(url)
        try: count=int(bool(json.loads(body).get("title")))
        except Exception: count=0
    else: raise ValueError(kind)
    if kind=="arctic_scoped" and status==422:
        try:
            d=json.loads(body).get("detail",[])
            detail=d[0] if isinstance(d,list) and d else d
            if isinstance(detail,dict):
                result["validation_field"]=str(detail.get("loc",[]))[:80]
                result["validation_type"]=str(detail.get("type",""))[:60]
                result["validation_msg"]=str(detail.get("msg","")).replace(query,"<term>")[:120]
            elif isinstance(detail,str):
                result["validation_msg"]=detail.replace(query,"<term>")[:120]
        except Exception: pass
    result.update(http=status,valid_public_records=count)
    if err: result["error"]=err
    return result

TASKS=[
    ("x_fxtwitter",""),("x_vxtwitter",""),("ig_profile",""),("telegram_preview",""),("telegramme",""),
    ("opentg",TARGET),("opentg",CONTROL),
    ("arctic_scoped",TARGET),("arctic_scoped",CONTROL),("arctic_subreddit",""),("reddit_public",""),
    ("misskey_m544",TARGET),("misskey_m544",CONTROL),
    ("misskey_sushi",TARGET),("misskey_sushi","섹트"),("misskey_sushi","뒷계"),("misskey_sushi",CONTROL),
    ("invidious",TARGET),("invidious",CONTROL),
    ("youtube_oembed",""),("tiktok_oembed","")
]

def nostr(relay,query):
    result={"source":"nostr:"+relay.split("/")[2],"query":"control" if query==CONTROL else ("target:"+str(("일탈계","섹트","뒷계").index(query)+1) if query in ("일탈계","섹트","뒷계") else "other") }
    try:
        import websocket
        conn=websocket.create_connection(relay,timeout=7,header=["User-Agent: "+UA])
        conn.settimeout(7)
        conn.send(json.dumps(["REQ","intersection-no-cost-check",{"kinds":[1],"search":query,"limit":10}]))
        n=0; matched=0
        cutoff=time.monotonic()+7
        while time.monotonic()<cutoff and n<25:
            try: msg=json.loads(conn.recv())
            except websocket.WebSocketTimeoutException: break
            if not isinstance(msg,list):continue
            if msg[0]=="EOSE":break
            if msg[0]=="EVENT" and len(msg)>2 and isinstance(msg[2],dict):
                n+=1
                if query in str(msg[2].get("content","")):matched+=1
            if msg[0]=="CLOSED":break
        conn.close()
        result.update(http=101,events=n,exact_keyword_matches=matched)
    except Exception as e:
        result.update(http=0,error=type(e).__name__)
    return result

def execute(task):
    try:return probe(*task)
    except Exception as e:
        return {"source":task[0],"query":"target" if task[1]==TARGET else "control","http":0,"error":type(e).__name__}

def main():
    with ThreadPoolExecutor(max_workers=6) as pool:
        for item in pool.map(execute,TASKS):
            print(json.dumps(item,ensure_ascii=False),flush=True)
    probes=[("wss://relay.nostr.band",TARGET),("wss://relay.nostr.band",CONTROL),
            ("wss://search.nos.today",TARGET),("wss://search.nos.today","섹트"),("wss://search.nos.today","뒷계"),("wss://search.nos.today",CONTROL)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for item in pool.map(lambda pair:nostr(*pair),probes):
            print(json.dumps(item,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
