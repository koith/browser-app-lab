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
alternative_urls=[
 "https://r.jina.ai/https://m.brand.naver.com/lottecinema",
 "https://r.jina.ai/https://search.shopping.naver.com/search/all?query="+urllib.parse.quote(QUERIES[0]),
 "https://www.google.com/search?q="+urllib.parse.quote('site:brand.naver.com/lottecinema/products 먼작귀'),
 "https://www.bing.com/search?q="+urllib.parse.quote('롯데시네마 먼작귀 네이버 예약 상품'),
 "https://search.naver.com/search.naver?query="+urllib.parse.quote(QUERIES[0]),
 "https://smartstore.naver.com/lottecinema",
 "https://m.smartstore.naver.com/lottecinema"
]
for url in alternative_urls:
 try:
  final,html=fetch(url)
  print("ALTERNATIVE_OK",urllib.parse.urlparse(final).netloc,"chars",len(html),"product_links",html.count("/products/"),"sample",repr(html[:160]))
  if "r.jina.ai/https://m.brand.naver.com/lottecinema" in url:
   for term in ["먼작귀","렌티큘러","띠부띠부","커버 참","C타입","/products/"]:
    m=re.search(re.escape(term),html,re.I)
    print("JINA_TERM",term,"present",bool(m),"context",repr(html[max(0,m.start()-180):m.start()+260] if m else ""))
   print("JINA_SAMPLE_TAIL",repr(html[-1700:]))
 except Exception as e:
  print("ALTERNATIVE_FAILED",urllib.parse.urlparse(url).netloc,type(e).__name__,str(e)[:160])
if good<2:
    print("FAIL: Cannot reliably query Naver store/search from runner.",file=sys.stderr)
    sys.exit(2)
print("PASS: Live Naver HTTP endpoints reachable, but listing/availability still must be validated.")
