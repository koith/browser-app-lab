#!/usr/bin/env python3
"""Read-only media enumeration of public, owner-authored mirror timelines.

This does NOT download or count gallery photos. It identifies whether a
normally accessible public web timeline exposes on-page photo links. No
authentication, CAPTCHA, proxies, search guessing or private URLs.
"""
from __future__ import annotations

import collections
import html
import json
import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

SOURCES = [
    {"model": "yui", "account": "super_yuisan", "url": "https://teapawt.net/super_yuisan"},
    {"model": "mimmi", "account": "Mimmi_official", "url": "https://teapawt.net/Mimmi_official"},
    {"model": "mimmi", "account": "Mimmi_official", "url": "https://www6.twstalker.com/Mimmi_official"},
    {"model": "mimmi", "account": "Mimmi_official", "url": "https://twoucan.com/profile/Mimmi_official"},
]
ATTRS=("src","data-src","data-original","data-lazy-src","srcset","data-srcset","href")

def media_urls(source, markup):
    doc=BeautifulSoup(markup,"html.parser")
    output=set()
    domains=collections.Counter()
    for el in doc.select("img,source,a[href],video"):
        for key in ATTRS:
            raw=el.get(key,"")
            if not raw:continue
            values=raw.split(",") if "srcset" in key else [raw]
            for value in values:
                value=html.unescape(value.strip().split(" ")[0])
                url=urljoin(source["url"],value)
                p=urlsplit(url)
                if p.scheme!="https" or not p.hostname:continue
                if (p.hostname.endswith("twimg.com") and "/media/" in p.path
                        or p.hostname==urlsplit(source["url"]).hostname and
                           re.search(r"\.(?:jpe?g|png|webp)(?:$|\?)",p.path,re.I)):
                    output.add(url)
                    domains[p.hostname]+=1
    pagination=[]
    for a in doc.select("a[href]"):
        u=urljoin(source["url"],a.get("href",""))
        p=urlsplit(u)
        if p.scheme=="https" and p.hostname==urlsplit(source["url"]).hostname and (
                re.search(r"(?:cursor|page|offset|max_position|after|until)=",p.query,re.I)
                or re.search(r"/(?:page|status)/\d+",p.path)):
            if u not in pagination:pagination.append(u)
    return output,domains,pagination

def run():
    result=[]
    for source in SOURCES:
        row={k:source[k] for k in ("model","account","url")}
        try:
            r=requests.get(source["url"],timeout=(8,20),headers={
                "User-Agent":"Mozilla/5.0 (compatible; PublicCreatorPhotoDiscovery/1.0)",
                "Accept":"text/html,application/xhtml+xml"},allow_redirects=False)
            row["status"]=r.status_code
            row["html_bytes"]=len(r.content)
            if r.status_code==200 and r.url==source["url"] and "html" in r.headers.get("content-type","").lower():
                urls,domains,pages=media_urls(source,r.text)
                row["media_url_count"]=len(urls)
                row["media_host_counts"]=dict(domains)
                row["pagination_candidates"]=len(pages)
                row["article_elements"]=len(BeautifulSoup(r.text,"html.parser").select("article,.timeline-item,.tweet,.status"))
                row["page_contains_expected_handle"]=source["account"].casefold() in r.text.casefold()
                if source["model"]=="yui" and source["url"].startswith("https://teapawt.net/"):
                    from collect_teapawt_public import public_images_from_author,download_one
                    own,_,_=public_images_from_author(r.text,{
                        "id":"diagnostic","account":source["account"],"kind":"teapawt",
                        "url":source["url"]},source["url"])
                    probed=[]
                    for media in own[:4]:
                        saved,issue=download_one(media,source)
                        probed.append({"success":saved is not None,
                            "error":issue,"bytes":len(saved["bytes"]) if saved else 0})
                    row["direct_public_media_probes"]=probed
                soup=BeautifulSoup(r.text,"html.parser")
                row["sample_articles"]=[{
                    "tag":el.name,"class":el.get("class",[])[:4],
                    "data_username":el.get("data-username"),
                    "has_handle":source["account"].casefold() in el.get_text(" ",strip=True).casefold(),
                    "media_url_count":len(media_urls(source,str(el))[0])
                } for el in soup.select("article,.timeline-item,.tweet,.status")[:4]]
                row["next_link_candidates"]=[{
                    "label":a.get_text(" ",strip=True)[:40],
                    "href_path":urlsplit(urljoin(source["url"],a.get("href",""))).path[:150],
                    "query_keys":sorted(__import__("urllib.parse",fromlist=["parse_qs"]).parse_qs(
                        urlsplit(urljoin(source["url"],a.get("href",""))).query).keys())[:5]
                } for a in soup.select("a[href]") if any(t in a.get_text(" ",strip=True).lower()
                    for t in ("next","older","load more","다음","もっと","›","»"))][:8]
            else:
                row["media_url_count"]=0
        except requests.RequestException as e:
            row["error_type"]=type(e).__name__
        result.append(row)
        print("PUBLIC_PROFILE_MEDIA_PROBE",json.dumps(row,ensure_ascii=False),flush=True)
    return result

if __name__=="__main__":run()
