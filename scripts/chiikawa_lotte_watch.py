#!/usr/bin/env python3
"""Fail-closed Naver Lotte Cinema Chiikawa reservation watcher."""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from html import unescape

STORE="https://m.brand.naver.com/lottecinema"
QUERIES=["먼작귀 롯데시네마 렌티큘러 띠부띠부","먼작귀 롯데시네마 C타입 커버 참"]
PRODUCT=re.compile(r"(먼작귀|치이카와|ちいかわ)",re.I)
TYPE=re.compile(r"(렌티큘러|띠부띠부|C타입|커버.?참)",re.I)
SELL=re.compile(r"(예약구매|예약 구매|구매하기|바로구매|구매 가능)")
NOTSELL=re.compile(r"(품절|판매예정|판매 예정|구매불가|구매 불가|SOLD OUT|일시품절)",re.I)
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ReservationAvailabilityCheck/1.0)","Accept-Language":"ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req,timeout=18) as r:
        return r.geturl(),r.read(2_000_000).decode("utf-8","replace")
def check():
    # Only verified product detail pages can trigger alerts, never search snippets.
    candidates=set()
    for q in QUERIES:
        try:
            url,html=fetch("https://search.shopping.naver.com/search/all?query="+urllib.parse.quote(q))
            for m in re.finditer(r'https?[^"\\\s<>]+(?:brand\.naver\.com/lottecinema/products/|smartstore\.naver\.com/lottecinema/products/)[0-9]+',unescape(html)):
                candidates.add(m.group(0).replace("&amp;","&").split("?")[0])
        except Exception as e: print("Discovery unavailable:",type(e).__name__,str(e)[:120],file=sys.stderr)
    for url in sorted(candidates):
        try:
            final,html=fetch(url)
            clean=unescape(re.sub(r'<[^>]*>',' ',html))
            clean=re.sub(r'\s+',' ',clean)
            if not (PRODUCT.search(clean) and TYPE.search(clean)): continue
            if NOTSELL.search(clean): continue
            if not SELL.search(clean): continue
            # Avoid false positive from navigation/global copy: require product-specific
            # structured data indicating availability and an actual buy CTA.
            if not re.search(r'(?:InStock|https?://schema.org/InStock|"saleStatus"\s*:\s*"ON_SALE")',html,re.I): continue
            return {"url":final,"matched":clean[:350],"checked_at":datetime.now(timezone.utc).isoformat()}
        except Exception as e: print("Detail unavailable:",type(e).__name__,str(e)[:120],file=sys.stderr)
    return None
if __name__=="__main__":
    result=check()
    if result:
        with open(os.environ.get("GITHUB_OUTPUT","/tmp/chiikawa-result"),"a") as f:
            f.write("found=true\nproduct_url="+result["url"]+"\n")
        print(json.dumps(result,ensure_ascii=False))
    else: print("No independently verified purchasable product; no alert.")
