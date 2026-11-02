"""Validate competitor insight: discover URLs using an indexer, read originals at source.

Question: Can a free keyless indexer + the original public Threads post page yield
post text, source timestamp and media from the same code? This tests that path.
No credentials, login, private content, cookies or proxy/evasion; 3 searches +
up to 6 original GETs. Only aggregate counts are logged.
"""
from __future__ import annotations
import concurrent.futures
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import time

UA="IntersectionPublicSourceMethodValidation/1.0"
QUERY_TERMS=("커피","일탈계","섹트")
POST_PATH=re.compile(r"^/@([A-Za-z0-9._]+)/post/([A-Za-z0-9_-]+)/*$")
MAX_BYTES=3_800_000

class ScriptMeta(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.parts=[];self.scripts=[];self.meta={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="script" and ("data-sjs" in a or a.get("type")=="application/json"):
            self.active=True;self.parts=[]
        if tag=="meta" and a.get("property","").startswith("og:"):
            self.meta[a["property"]]=a.get("content","")
    def handle_data(self,s):
        if self.active:self.parts.append(s)
    def handle_endtag(self,tag):
        if tag=="script" and self.active:
            self.scripts.append("".join(self.parts))
            self.active=False;self.parts=[]

def read(url,body=None,headers=None):
    h={"User-Agent":UA,"Accept":"text/html, application/json"}
    h.update(headers or {})
    data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    if data:h["Content-Type"]="application/json"
    req=urllib.request.Request(url,headers=h,data=data,method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req,timeout=15) as res:
            return res.status,res.read(MAX_BYTES).decode("utf-8","replace"),res.geturl()
    except urllib.error.HTTPError as e:return e.code,"",""
    except Exception:return 0,"",""

def canonical(url):
    try:
        p=urllib.parse.urlsplit(url)
        if p.scheme!="https" or (p.hostname or "").removeprefix("www.") not in ("threads.com","threads.net"):return None
        match=POST_PATH.match(p.path)
        if not match:return None
        return ("https://www.threads.com"+p.path,match.group(2))
    except (ValueError,TypeError):return None

def by_code(data,code):
    todo=[data];limit=0
    while todo and limit<180000:
        x=todo.pop();limit+=1
        if isinstance(x,dict):
            if x.get("code")==code and (x.get("taken_at") or x.get("caption")):
                yield x
            todo.extend(x.values())
        elif isinstance(x,list):todo.extend(x)

def one_post(row,term):
    url,code=row
    http,html,final=read(url)
    final_ok=canonical(final)
    result={"http":http,"canonical_final":bool(final_ok and final_ok[1]==code),
        "bytes":len(html),"source_json_posts":0,"valid_timestamp":False,
        "recent_32_days":False,"exact_term_in_source":False,"has_image_or_video":False,
        "og_description_present":False,"og_image_present":False}
    if not html or not result["canonical_final"]:return result
    parser=ScriptMeta()
    try:parser.feed(html)
    except Exception:return result
    result["og_description_present"]=bool(parser.meta.get("og:description"))
    result["og_image_present"]=bool(parser.meta.get("og:image"))
    result["json_scripts"]=len(parser.scripts)
    now=datetime.now(timezone.utc).timestamp()
    for script in parser.scripts[:90]:
        try:obj=json.loads(script)
        except Exception:continue
        for post in by_code(obj,code):
            result["source_json_posts"]+=1
            if not isinstance(post,dict):continue
            caption=post.get("caption")
            body=str(caption.get("text") or "") if isinstance(caption,dict) else ""
            result["exact_term_in_source"]=result["exact_term_in_source"] or term in body
            try:stamp=float(post.get("taken_at"))
            except (ValueError,TypeError):stamp=0
            if 1100000000<=stamp<=now+86400:
                result["valid_timestamp"]=True
                result["recent_32_days"]=result["recent_32_days"] or stamp>=now-32*86400
            result["has_image_or_video"]=result["has_image_or_video"] or bool(
                post.get("image_versions2") or post.get("video_versions") or post.get("carousel_media"))
    return result

def probe(term):
    label="control" if term=="커피" else ("project1" if term=="일탈계" else "project2")
    status,body,_=read("https://api.keenable.ai/v1/search/public",{
        "query":'site:threads.com "'+term+'"',"max_results":20
    },{"X-Keenable-Title":"intersection-research","Accept":"application/json"})
    try:raw=json.loads(body);rows=raw.get("results",[])
    except (ValueError,TypeError):rows=[]
    refs=[];seen=set()
    for row in rows if isinstance(rows,list) else []:
        item=canonical(row.get("url","")) if isinstance(row,dict) else None
        if not item or item[1] in seen:continue
        seen.add(item[1]);refs.append(item)
    samples=[one_post(x,term) for x in refs[:2]]
    print(json.dumps({"method":"index_to_threads_original","keyword":label,
        "search_http":status,"index_results":len(rows),"canonical_candidates":len(refs),
        "originals_checked":len(samples),
        "original_http_200":sum(x["http"]==200 for x in samples),
        "canonical_originals":sum(x["canonical_final"] for x in samples),
        "matched_embedded_post":sum(x["source_json_posts"]>0 for x in samples),
        "dated_originals":sum(x["valid_timestamp"] for x in samples),
        "recent_originals":sum(x["recent_32_days"] for x in samples),
        "keyword_in_source_text":sum(x["exact_term_in_source"] for x in samples),
        "og_descriptions":sum(x["og_description_present"] for x in samples),
        "og_images":sum(x["og_image_present"] for x in samples),
        "source_media":sum(x["has_image_or_video"] for x in samples)
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(probe,QUERY_TERMS))
