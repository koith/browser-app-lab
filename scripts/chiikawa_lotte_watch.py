#!/usr/bin/env python3
"""Chiikawa Lotte reservation listing monitor.

Never reports confirmed purchasability merely from product listing.
GitHub Issue mentions/assignees are the delivery channel, not Gmail inbox.
"""
import os
import re
import subprocess
import sys
import urllib.request
from html import unescape

STORE = "https://m.brand.naver.com/lottecinema"
CATEGORY = STORE + "/category/4c667f4dac7145f3808a651aaade854b?cp=1"
SOURCES = ("https://r.jina.ai/" + CATEGORY, "https://r.jina.ai/" + STORE)
PRODUCT = re.compile(r"먼작귀|치이카와|ちいかわ", re.I)
TARGETS = (
    ("lenticular", re.compile(r"렌티큘러|띠부띠부|렌티.?씰", re.I), "렌티큘러 스티커"),
    ("usb-charm", re.compile(r"C\s*타입|USB[\s-]*C|커버\s*참|케이블.{0,15}커버", re.I), "USB-C 커버 참"),
)
CARD = re.compile(
    r"\[상품 상세보기\]\((https://(?:m\.)?brand\.naver\.com/lottecinema/products/\d+)\)\s*\*\*(.{2,250}?)\*\*",
    re.S,
)


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ChiikawaAvailabilityWatcher/1.0)",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "X-Cache-Tolerance": "45",
        },
    )
    with urllib.request.urlopen(req, timeout=22) as response:
        return response.geturl(), response.read(2_000_000).decode("utf-8", "replace")


def parse_catalog(document):
    results = {}
    for card in CARD.finditer(document):
        url, raw_title = card.groups()
        title = re.sub(r"\s+", " ", unescape(raw_title)).strip()
        if not PRODUCT.search(title):
            continue
        for kind, pattern, label in TARGETS:
            if pattern.search(title):
                results.setdefault(kind, {"kind": kind, "label": label, "title": title, "url": url})
    return list(results.values())


def check():
    seen = {}
    healthy = 0
    for source in SOURCES:
        try:
            resolved, body = fetch(source)
            if "롯데시네마" not in body or "/products/" not in body:
                print("SOURCE_INCOMPLETE", resolved, "chars", len(body), flush=True)
                continue
            healthy += 1
            products = parse_catalog(body)
            print("SOURCE_OK", resolved, "chars", len(body), "matching_categories", len(products), flush=True)
            for item in products:
                seen.setdefault(item["kind"], item)
        except Exception as exc:
            print("SOURCE_FAILED", source, type(exc).__name__, str(exc)[:160], file=sys.stderr, flush=True)
    if healthy == 0:
        raise RuntimeError("Both independent catalog reads unavailable or incomplete")
    return list(seen.values())


def send_issue_alerts(products):
    """Require GitHub Token and use GitHub's own API through gh; retry on failures."""
    if not products:
        return
    if not os.environ.get("GH_TOKEN"):
        print("NO_GH_TOKEN: cannot send alerts", file=sys.stderr)
        raise RuntimeError("Missing GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "koith/browser-app-lab")
    existing = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "300",
         "--json", "title", "--jq", ".[].title"],
        check=True, capture_output=True, text=True
    ).stdout.splitlines()
    for item in products:
        issue_title = "[먼작귀 예약상품 등록 감지] " + item["label"]
        if issue_title in existing:
            print("ALREADY_ALERTED", issue_title, flush=True)
            continue
        body = (
            "@koith 롯데시네마 브랜드스토어에 이번 먼작귀 예약 대상 상품이 "
            "등록된 것을 감지했습니다.\n\n"
            "상품: " + item["title"] + "\n"
            "상품 링크: " + item["url"] + "\n\n"
            "**주의: 상품 등록 감지이며 구매 버튼 활성화는 별도 확인이 필요합니다.**"
        )
        created = subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--title", issue_title,
             "--assignee", "koith", "--body", body],
            check=True, capture_output=True, text=True
        )
        print("ALERT_CREATED", issue_title, created.stdout.strip(), flush=True)
        existing.append(issue_title)


def main():
    try:
        products = check()
        if products:
            print("TARGETS", [(p["kind"], p["url"]) for p in products], flush=True)
            send_issue_alerts(products)
        else:
            print("HEALTHY_NO_TARGET_YET", flush=True)
        return 0
    except Exception as exc:
        print("WATCH_FAILED", type(exc).__name__, str(exc)[:180], file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
