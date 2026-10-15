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
RECENT = STORE + "/category/2sWE0vIa6tWNMMW47PDeX_ALL_PRODUCT?st=RECENT"
SOURCES = ("https://r.jina.ai/" + CATEGORY, "https://r.jina.ai/" + STORE, "https://r.jina.ai/" + RECENT)
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


def buy_button_visible(document, item):
    """Only a target product detail page's active-looking buy CTA is a buying signal."""
    header = document[:350]
    if not PRODUCT.search(header):
        return False
    wanted = next((matcher for kind, matcher, _ in TARGETS if kind == item["kind"]), None)
    if not wanted or not wanted.search(header):
        return False
    for match in re.finditer(r"(?m)^\s*구매하기\s*$", document):
        nearby = document[max(0, match.start()-140):match.end()+140]
        if re.search(r"품절|판매\s*예정|판매\s*종료|구매\s*불가|판매\s*중지", nearby):
            continue
        return True
    return False


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
    for item in seen.values():
        item["stage"] = "listed"
        try:
            detail_url, detail = fetch("https://r.jina.ai/" + item["url"])
            if buy_button_visible(detail, item):
                item["stage"] = "buy_button"
            print("DETAIL_STAGE", item["kind"], item["stage"], detail_url, flush=True)
        except Exception as error:
            print("DETAIL_UNAVAILABLE", item["kind"], type(error).__name__, str(error)[:160], file=sys.stderr, flush=True)
    return list(seen.values())


def send_ntfy(item):
    """Independent high-priority phone push, separate from Gmail-filtered GitHub mail."""
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return
    destination = "https://ntfy.sh/" + topic
    body = (
        ("먼작귀 예약상품 구매 버튼 발견\n" if item.get("stage") == "buy_button" else "롯데시네마 먼작귀 예약상품 등록 감지\n")
        + item["label"] + "\n"
        + item["title"] + "\n"
        + item["url"] + "\n"
        + "※ 페이지 표시를 감지한 것이며 실제 결제 가능 여부는 직접 확인."
    ).encode("utf-8")
    request = urllib.request.Request(
        destination,
        data=body,
        headers={
            "Title": "Chiikawa Lotte reservation item found",
            "Priority": "5",
            "Click": item["url"],
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=14) as response:
        if response.status != 200:
            raise RuntimeError("ntfy publish failed: " + str(response.status))
        print("NTFY_PUBLISHED", item["kind"], response.status, flush=True)


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
        buy_title = "[먼작귀 구매하기 버튼 감지] " + item["label"]
        listed_title = "[먼작귀 예약상품 등록 감지] " + item["label"]
        issue_title = buy_title if item.get("stage") == "buy_button" else listed_title
        if item.get("stage") != "buy_button" and buy_title in existing:
            print("BUY_STAGE_ALREADY_ALERTED", item["kind"], flush=True)
            continue
        if issue_title in existing:
            print("ALREADY_ALERTED", issue_title, flush=True)
            continue
        prefix = (
            "@koith 롯데시네마 먼작귀 상품 상세페이지에서 **구매하기 버튼 표시**를 확인했습니다.\n\n"
            if item.get("stage") == "buy_button"
            else "@koith 롯데시네마 먼작귀 예약 대상 상품 **등록**을 감지했습니다.\n\n"
        )
        body = (
            prefix
            + "상품: " + item["title"] + "\n"
            + "상품 링크: " + item["url"] + "\n\n"
            + "**주의: 실제 주문·결제가 가능한지는 상품 페이지에서 직접 최종 확인하세요.**"
        )
        try:
            send_ntfy(item)
        except Exception as error:
            print("NTFY_FAILED", type(error).__name__, str(error)[:160], file=sys.stderr, flush=True)
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
