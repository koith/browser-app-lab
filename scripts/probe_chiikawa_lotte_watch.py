#!/usr/bin/env python3
"""End-to-end live catalog probe run from a real GitHub Actions runner."""
import sys
from chiikawa_lotte_watch import SOURCES, CARD, fetch, check, parse_catalog

healthy = 0
for source in SOURCES:
    try:
        final, text = fetch(source)
        cards = CARD.findall(text)
        print("LIVE_READER_OK", final, "chars", len(text), "parseable_cards", len(cards))
        print("LIVE_SAMPLE_TITLES", [title.strip()[:95] for _, title in cards[:3]])
        print("TARGETS_MATCHED", [(x["kind"],x["url"]) for x in parse_catalog(text)])
        if "롯데시네마" in text and len(cards) > 0:
            healthy += 1
    except Exception as error:
        print("LIVE_READER_FAILED", source, type(error).__name__, str(error)[:200])
if healthy == 0:
    print("FAIL: no usable store catalog from GitHub runner", file=sys.stderr)
    sys.exit(2)
print("LIVE_CATALOG_PROBE_PASS: real product cards were fetched and parsed.")
print("IMPORTANT: future 1-minute cache refresh, exact sale button and iOS push are not proven by this probe.")


for item_url in (
    "https://m.brand.naver.com/lottecinema/products/12369795868",
    "https://m.brand.naver.com/lottecinema/products/13751593118",
):
    try:
        resolved,body=fetch("https://r.jina.ai/"+item_url)
        print("DETAIL_READ",item_url,"chars",len(body),"page",repr(body[:160]))
        for term in ("구매하기","바로구매","예약구매","판매예정","품절","장바구니","판매중","재고","상품상세"):
            at=body.find(term)
            print("DETAIL_MARKER",item_url.split("/")[-1],term,at,"context",repr(body[max(0,at-70):at+100] if at>=0 else ""))
    except Exception as e:
        print("DETAIL_FAILED",item_url,repr(e))
