#!/usr/bin/env python3
"""Read-only probe of ordinary public Mimmi Instagram preview pages.

Only identity-verified photo pages. No login, guessed private endpoints,
authentication bypass, or photo publishing. Inspect image source hosts and
HTTP results before selecting an acquisition strategy.
"""
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
import requests,json,collections,re

PAGES=["https://imginn.com/mimmissu17/",
       "https://imginn.com/p/Da3E4Bck_Wz/",
       "https://imginn.com/p/DQn4BBmkzTz/"]
ALLOWED={"imginn.com","www.imginn.com"}
HEADERS={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
         "Accept":"text/html,application/xhtml+xml"}
def run():
    result=[]
    for page_url in PAGES:
        row={"url":page_url}
        try:
            r=requests.get(page_url,timeout=(8,22),headers=HEADERS,allow_redirects=False)
            row.update(status=r.status_code,content_type=r.headers.get("content-type","")[:90],bytes=len(r.content))
            if r.status_code!=200 or "html" not in r.headers.get("content-type","").lower():result.append(row);continue
            soup=BeautifulSoup(r.content,"html.parser")
            row["handle_present"]="mimmissu17" in soup.get_text(" ",strip=True).casefold()
            photo_urls=[]
            post_urls=[]
            for e in soup.select("img[src],img[data-src],img[data-original],a[href],source[srcset],meta[content]"):
                for attr in ("src","data-src","data-original","href","srcset","content"):
                    raw=e.get(attr,"")
                    if not raw:continue
                    first=raw.split(",")[0].strip().split()[0]
                    u=urljoin(page_url,first)
                    p=urlsplit(u)
                    if p.scheme!="https" or not p.hostname:continue
                    if p.hostname in ALLOWED and re.fullmatch(r"/p/[A-Za-z0-9_-]{9,15}/?",p.path):
                        if u not in post_urls:post_urls.append(u)
                    if (re.search(r"\.(?:jpe?g|png|webp)(?:$|\?)",p.path,re.I)
                            or any(s in p.hostname for s in ("instagram","cdninstagram","fbcdn"))):
                        if u not in photo_urls:photo_urls.append(u)
            row["visible_post_links"]=len(post_urls)
            row["visible_image_links"]=len(photo_urls)
            row["image_hosts"]=dict(collections.Counter(urlsplit(u).hostname for u in photo_urls))
            attempts=[]
            for url in photo_urls[:4]:
                host=urlsplit(url).hostname
                if not host or not (host in ALLOWED or
                     host.endswith(".cdninstagram.com") or host.endswith(".fbcdn.net") or host=="cdninstagram.com"):
                    continue
                try:
                    with requests.get(url,headers={"User-Agent":HEADERS["User-Agent"],"Accept":"image/*"},
                                      timeout=(8,16),stream=True,allow_redirects=False) as reply:
                        attempts.append({"host":host,"status":reply.status_code,
                            "type":reply.headers.get("content-type","").split(";")[0]})
                except requests.RequestException as err:
                    attempts.append({"host":host,"error":type(err).__name__})
            row["public_photo_response_samples"]=attempts
        except requests.RequestException as err:
            row["error_type"]=type(err).__name__
        result.append(row)
        print("MIMMI_IMGINN_PUBLIC_PROBE",json.dumps(row,ensure_ascii=False),flush=True)
    return result
if __name__=="__main__":run()
