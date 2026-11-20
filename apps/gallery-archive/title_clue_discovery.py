#!/usr/bin/env python3
"""Title-first catalogue discovery: separate hints, verified editions and files.

Metadata only. Search and page tasks are durable; blocked/failed tasks are
not marked inspected. No protected media, authentication or bot bypass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict, deque
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from source_name_ledger import LEDGER, key
from source_alias_search import hydrate_all_registered_works, https_page, page_matches, source_headings

ROOT = Path(__file__).resolve().parents[2]
ENGINES = {"google": "https://www.google.com/search", "yandex": "https://yandex.com/search/"}
ENGINE_PARAM = {"google": "q", "yandex": "text"}
PUBLISHERS = {
    "artgravia": ("ArtGravia", "AG", "아트그라비아"),
    "sweetbox": ("SWEETBOX", "SWTB", "스위트박스"),
    "djawa": ("DJAWA", "DJAWA Photo", "디자와"),
    "milkybomb": ("MilkyBomb", "Milky Bomb"),
    "yo u": ("Yo-U", "Yo U"),
    "bcut": ("BCUT", "B-CUT"),
    "crazy giant": ("CRAZY GIANT", "크레이지 자이언트"),
}
# Dictionary translations are SEARCH HINTS, never verified alternate titles.
WORDS = {
    "summer": ("여름", "夏", "夏天"), "winter": ("겨울", "冬", "冬天"),
    "night": ("밤", "夜", "夜晚"), "cat": ("고양이", "猫", "ねこ"),
    "green": ("초록", "绿色", "緑"), "white": ("하얀", "白色", "白"),
    "black": ("검정", "黑色", "黒"), "blue": ("파랑", "蓝色", "青"),
    "dream": ("꿈", "梦", "夢"), "heart": ("하트", "心", "ハート"),
    "party": ("파티", "派对", "パーティー"), "flower": ("꽃", "花", "花"),
    "school": ("학교", "学校", "学校"), "sunshine": ("햇살", "阳光", "日差し"),
}
NOISE = set("photo photos photobook public preview samples sample video videos only album sexy girl ai enhanced official gallery images vol issue part edition ver the and of in x 공개 사진 미리보기 화보 공개본 보정본 샘플 원본".split())
ORDINAL = re.compile(r"(?i)(?<!\w)(vol(?:ume)?|no|issue|part|#)[.\s_-]*0*(\d{1,5})(?!\d)")
COUNT = re.compile(r"(?i)\b\d+\s*(?:photos?|videos?|pics?|images?|p\b)")
# Avoid treating a real image count or year as an edition identifier.
def normalize(text):
    return unicodedata.normalize("NFKC", str(text)).strip()

def title_clues(title, aliases=(), publisher="", album_id=""):
    text = normalize(title)
    cleaned = COUNT.sub(" ", text)
    cleankey = key(cleaned)
    context = key(cleaned + " " + publisher + " " + album_id)
    publishers = []
    for family in PUBLISHERS.values():
        if any(re.search(r"(?<!\w)"+re.escape(key(a))+r"(?!\w)", context) for a in family):
            publishers.extend(family)
        # Compacted abbreviated codes, e.g. AG639 / SWTB22, are explicit hints.
        elif any(re.search(r"(?<!\w)"+re.escape(a)+r"\s*0*\d{1,5}(?!\d)", cleaned, re.I)
                 for a in family if a.isascii() and len(a)<6):
            publishers.extend(family)
    editions = [(m.group(1).lower(), str(int(m.group(2)))) for m in ORDINAL.finditer(cleaned)]
    for a in publishers:
        if a.isascii() and " " not in a:
            editions.extend(("code", str(int(m.group(1)))) for m in re.finditer(
                r"(?<!\w)"+re.escape(a)+r"[.\s_-]*0*(\d{1,5})(?!\d)", cleaned, re.I))
    editions = list(dict.fromkeys(editions))
    stop = NOISE | {w for a in (*aliases, *publishers) for w in key(a).split()}
    title_words = [w for w in re.findall(r"[^\W\d_]+", cleankey, flags=re.UNICODE)
                   if len(w)>=2 and w not in stop]
    title_words = list(dict.fromkeys(title_words))
    return {"title":text, "publishers":list(dict.fromkeys(publishers)),
            "editions":editions, "words":title_words,
            "translations":list(dict.fromkeys(t for w in title_words for t in WORDS.get(w, ())))}

def query_families(title, aliases, publisher="", album_id=""):
    c = title_clues(title, aliases, publisher, album_id)
    f = defaultdict(list)
    def add(family, *parts):
        q = " ".join(p for p in parts if p).strip()
        if q and len(q)<=240 and q not in f[family]:
            f[family].append(q)
    for a in aliases: add("model", a)
    for p in c["publishers"]: add("publisher", p)
    for w in c["words"]: add("word", w)
    for t in c["translations"]: add("translated_word", t)
    for kind, n in c["editions"]:
        add("number", n)
        for p in c["publishers"]:
            add("publisher_number", p, n)
            if p.isascii() and len(p)<7 and " " not in p:
                add("compact_code", p+n)
            add("publisher_number", p, "Vol."+n)
        for a in aliases:
            add("model_number", a, n)
    for a in aliases:
        for w in c["words"]+c["translations"]:
            add("model_word", a, w)
        for p in c["publishers"]:
            add("model_publisher", a, p)
            for kind,n in c["editions"]: add("model_code", a, p, n)
        add("full_title", a, '"'+c["title"]+'"')
    if c["words"]: add("title_words", " ".join(c["words"]))
    return dict(f)

def interleave(families):
    queues = deque((name, deque(values)) for name,values in families.items() if values)
    seen=set()
    while queues:
        name, q = queues.popleft()
        v=q.popleft()
        if v not in seen:
            seen.add(v); yield name,v
        if q: queues.append((name,q))

def catalog(model, root=ROOT):
    db=json.loads((root/"apps/gallery-archive/source-names.json").read_text())
    hydrate_all_registered_works(db,model,root)
    aliases=[x["name"] for x in db["model_names"][model]]
    records={}
    base=root/"apps"/(model+"-gallery")
    for filename in ("public-work-pages.json","owner-index.json","albums.json","publisher-catalogue.json"):
        p=base/filename
        if not p.is_file():continue
        for row in json.loads(p.read_text()).get("albums",[]):
            title=row.get("title","")
            if not title:continue
            rid=row.get("id") or "catalogue-"+hashlib.sha256((str(row.get("publisher",""))+title).encode()).hexdigest()[:16]
            r=records.setdefault(rid,{"id":rid,"titles":[],"publisher":str(row.get("publisher",""))})
            if title not in r["titles"]:r["titles"].append(title)
            if not r["publisher"]:r["publisher"]=str(row.get("publisher",""))
    for work, names in db["works"].items():
        if not work.startswith(model+":"):continue
        rid=work.split(":",1)[1]
        r=records.setdefault(rid,{"id":rid,"titles":[],"publisher":""})
        for row in names:
            if row["name"] not in r["titles"]:r["titles"].append(row["name"])
    return db, aliases, list(records.values())

def plan(model, root=ROOT):
    db,aliases,records=catalog(model,root)
    queues=deque()
    for r in records:
        families=defaultdict(list)
        for title in r["titles"]:
            for kind, values in query_families(title,aliases,r["publisher"],r["id"]).items():
                families[kind].extend(values)
        queues.append((r["id"],iter(interleave({k:list(dict.fromkeys(v)) for k,v in families.items()}))))
    # Interleave works, not simply the first N queries of the first work.
    out={}; counts=Counter()
    while queues:
        rid, items=queues.popleft()
        try:family,q=next(items)
        except StopIteration:continue
        entry=out.setdefault(q,{"query":q,"families":[],"works":[]})
        if family not in entry["families"]:entry["families"].append(family)
        if rid not in entry["works"]:entry["works"].append(rid)
        counts[family]+=1
        queues.append((rid,items))
    return db,aliases,records,list(out.values()),dict(counts)

def canonical(url):
    try:
        p=urlsplit(url)
        url=urlunsplit(p._replace(fragment=""))
        return url if https_page(url) else None
    except (TypeError,ValueError):return None

def search_hits(raw, engine):
    soup=BeautifulSoup(raw,"html.parser")
    selectors={"google":"div#search a[href], div#rso a[href]", 
               "yandex":"li.serp-item a[href], div.serp-item a[href], a.OrganicTitle-Link[href]"}
    hits={}
    for a in soup.select(selectors[engine]):
        href=a.get("href","")
        if href.startswith("/url?"):
            q=parse_qs(urlsplit(href).query); href=(q.get("q") or q.get("url") or [""])[0]
        u=canonical(href)
        if not u:continue
        h=urlsplit(u).hostname
        if any(h==x or h.endswith("."+x) for x in ("google.com","yandex.com","yandex.ru")):continue
        hits[u]=a.get_text(" ",strip=True)[:220]
    return hits

class Queue:
    def __init__(self, filename):
        self.db=sqlite3.connect(str(filename))
        self.db.execute("CREATE TABLE IF NOT EXISTS task (id INTEGER PRIMARY KEY, kind TEXT, value TEXT, engine TEXT, status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0, detail TEXT DEFAULT '', UNIQUE(kind,value,engine))")
        self.db.execute("CREATE TABLE IF NOT EXISTS sites(host TEXT PRIMARY KEY, evidence TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS observations(url TEXT, work TEXT, title TEXT, UNIQUE(url,work))")
        self.db.commit()
    def add(self,kind,value,engine=""):
        self.db.execute("INSERT OR IGNORE INTO task(kind,value,engine) VALUES(?,?,?)",(kind,value,engine)); self.db.commit()
    def next(self):
        # Page tasks precede new searches, but retain all queued search work.
        return self.db.execute("SELECT id,kind,value,engine FROM task WHERE status='pending' ORDER BY CASE kind WHEN 'page' THEN 0 ELSE 1 END,id LIMIT 1").fetchone()
    def finish(self,id,status,detail=""):
        self.db.execute("UPDATE task SET status=?,attempts=attempts+1,detail=? WHERE id=?",(status,detail,id)); self.db.commit()
    def site(self,host,evidence):
        self.db.execute("INSERT OR IGNORE INTO sites VALUES (?,?)",(host,evidence)); self.db.commit()
    def observation(self,url,work,title):
        self.db.execute("INSERT OR IGNORE INTO observations VALUES (?,?,?)",(url,work,title));self.db.commit()
    def report(self):
        return {"queue":{k+":"+s:n for k,s,n in self.db.execute("SELECT kind,status,count(*) FROM task GROUP BY kind,status")},
                "sites":[{"host":h,"evidence":e} for h,e in self.db.execute("SELECT host,evidence FROM sites ORDER BY host")],
                "observations":[{"url":u,"work":w,"title":t} for u,w,t in self.db.execute("SELECT url,work,title FROM observations ORDER BY work,url")]}

class PublicMetadata:
    """Ordinary public HTML, robots policy and strict no-redirect boundary."""
    def __init__(self):
        self.session=requests.Session()
        self.agent="PersonalPublicCatalogueResearch/1.0"
        self.robots={}
    def get(self,url):
        url=canonical(url)
        if not url:return None,"unsafe_url"
        host=urlsplit(url).netloc
        try:
            if host not in self.robots:
                robot=self.session.get("https://"+host+"/robots.txt",headers={"User-Agent":self.agent},timeout=(4,6),allow_redirects=False)
                rp=RobotFileParser()
                if robot.status_code==200:rp.parse(robot.text.splitlines())
                elif robot.status_code==404:rp.parse([])
                else:return None,"robots_unavailable_"+str(robot.status_code)
                self.robots[host]=rp
            if not self.robots[host].can_fetch(self.agent,url):return None,"robots_disallowed"
            with self.session.get(url,headers={"User-Agent":self.agent,"Accept":"text/html"},timeout=(4,8),allow_redirects=False,stream=True) as r:
                if r.status_code!=200:return None,"http_"+str(r.status_code)
                if "html" not in r.headers.get("content-type","").lower():return None,"not_html"
                chunks=[];size=0
                for part in r.iter_content(chunk_size=65536):
                    size+=len(part)
                    if size>2_000_000:return None,"oversized"
                    chunks.append(part)
                raw=b"".join(chunks).decode(r.encoding or "utf-8",errors="replace")
                if re.search(r"captcha|unusual traffic|verify (?:you are|that you are) human",raw[:12000],re.I):
                    return None,"access_boundary"
                return raw,"ok"
        except requests.RequestException as e:return None,type(e).__name__

def related_links(raw,url,model_words):
    soup=BeautifulSoup(raw,"html.parser")
    host=urlsplit(url).hostname
    found=set()
    for a in soup.select("a[href]"):
        target=canonical(urljoin(url,a.get("href","")))
        if not target or urlsplit(target).hostname!=host or target==url:continue
        label=key(a.get_text(" ",strip=True)+" "+a.get("href",""))
        rel=a.get("rel",[])
        if (any(w and w in label for w in model_words)
            or any(x in rel for x in ("next","prev"))
            or re.search(r"(?:^| )(?:next|previous|more|page|category|tag|model|artist|publisher|portfolio)(?: |$)",label)
            or re.fullmatch(r"\d+",a.get_text(" ",strip=True))):
            found.add(target)
    return sorted(found)

def process(queue, db, aliases, model, budget, transport):
    clues={key(a) for a in aliases if len(key(a))>=2}
    for names in db["works"].values():
        for r in names:
            clues.update(key(p) for p in title_clues(r["name"],aliases)["publishers"])
    for _ in range(budget):
        task=queue.next()
        if not task:break
        id,kind,value,engine=task
        url=ENGINES[engine]+"?"+urlencode({ENGINE_PARAM[engine]:value}) if kind=="search" else value
        raw,status=transport.get(url)
        if raw is None:
            queue.finish(id,"blocked" if status.startswith(("robots","http_401","http_403","access_boundary")) else "failed",status)
            continue
        if kind=="search":
            hits=search_hits(raw,engine)
            for u in hits:queue.add("page",u)
            # Empty/unparseable SERPs are not evidence that no sites exist.
            queue.finish(id,"inspected" if hits else "unparsed",str(len(hits)))
            continue
        heading,context=source_headings(raw)
        evidence=key(heading+" "+context)
        matching=[w for w in db["works"] if w.startswith(model+":") and page_matches(w,heading,context)]
        weak=any(re.search(r"(?<!\w)"+re.escape(c)+r"(?!\w)",evidence) for c in clues)
        if matching or weak:
            host=urlsplit(url).hostname
            queue.site(host,url)
            # Weak clues open a research site, never promote a title or media.
            for u in related_links(raw,url,clues):queue.add("page",u)
        if len(matching)==1:queue.observation(url,matching[0],heading[:220])
        queue.finish(id,"inspected",str(len(matching)))
    return queue.report()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=["yui","mimmi"],required=True)
    p.add_argument("--state",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--budget",type=int,default=0)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--retry-failed",action="store_true")
    a=p.parse_args()
    if not 0<=a.budget<=200:raise ValueError("invalid execution budget")
    db,aliases,records,queries,types=plan(a.model,a.root)
    q=Queue(a.state)
    for item in queries:
        for engine in ENGINES:q.add("search",item["query"],engine)
    if a.retry_failed:
        q.db.execute("UPDATE task SET status='pending' WHERE status IN ('failed','unparsed')")
        q.db.commit()
    report=process(q,db,aliases,a.model,a.budget,PublicMetadata()) if a.budget else q.report()
    result={"model":a.model,"catalogue_records":len(records),"query_count":len(queries),
            "query_families":types,"research_only":True,"physical_new_files":0,**report}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("TITLE_CLUE_DISCOVERY",json.dumps({k:v for k,v in result.items() if k not in ("sites","observations")},ensure_ascii=False))
if __name__=="__main__":main()
