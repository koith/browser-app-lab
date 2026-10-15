#!/usr/bin/env python3
"""Live network smoke probe in GitHub-hosted runner, no purchase, no notification."""
import re, sys, urllib.parse
from chiikawa_lotte_watch import fetch, QUERIES, check
urls=["https://m.brand.naver.com/lottecinema"]+["https://search.shopping.naver.com/search/all?query="+urllib.parse.quote(q) for q in QUERIES]
good=0
for url in urls:
    try:
        final,html=fetch(url)
        good+=1
        titles=re.search(r"<title[^>]*>(.{0,180}?)</title>",html,re.I|re.S)
        print("NETWORK_OK",urllib.parse.urlparse(final).netloc,"chars",len(html),"title",repr(titles.group(1)[:90] if titles else None),"product_links",html.count("/products/"),"embedded_products",html.count("productNo"))
    except Exception as e:
        print("NETWORK_FAILED",urllib.parse.urlparse(url).netloc,type(e).__name__,str(e)[:200])
print("TARGET_FOUND",repr(check()))
if good<2:
    print("FAIL: Cannot reliably query Naver store/search from runner.",file=sys.stderr)
    sys.exit(2)
print("PASS: Live Naver HTTP endpoints reachable, but listing/availability still must be validated.")
