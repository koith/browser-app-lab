"""Aggregate-only current Wikipedia page attention, not purchase intent.

Official Wikimedia Analytics API, CC0 1.0. Exactly six public product or
product-category article titles (no users/profiles/SNS). Daily bot-filtered
article views: last 7 complete days compared with the previous 7 days.

Wikimedia Analytics API policies: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html
"""
from __future__ import annotations

from datetime import date, timedelta
import argparse
import json
import os
from pathlib import Path
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

SOURCE_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
DOC_URL = "https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/"
PROJECT = "en.wikipedia"
# Article-level counts are not comparable to product sales; some titles represent
# broad categories and others are particular devices.
ARTICLES = (
    ("ps5", "PlayStation 5", "PlayStation_5", "device"),
    ("switch2", "Nintendo Switch 2", "Nintendo_Switch_2", "device"),
    ("airpods", "AirPods Pro", "AirPods_Pro", "device_family"),
    ("robotvac", "로봇청소기", "Robot_vacuum_cleaner", "category"),
    ("espresso", "에스프레소 머신", "Espresso_machine", "category"),
    ("standingdesk", "스탠딩 데스크", "Standing_desk", "category"),
)
MAX_BODY = 65_536
MAX_DAY_VIEWS = 100_000_000


def _day_values(end: date) -> list[str]:
    return [(end - timedelta(days=i)).strftime("%Y%m%d") for i in range(13, -1, -1)]


def fetch(title: str, start: str, end: str) -> dict:
    allowed = {a[2] for a in ARTICLES}
    if title not in allowed:
        raise ValueError("Wikipedia article outside the reviewed allowlist")
    if len(start) != 8 or len(end) != 8 or not start.isdigit() or not end.isdigit():
        raise ValueError("invalid Wikimedia date bounds")
    url = (SOURCE_URL + "/en.wikipedia/all-access/user/" +
           quote(title, safe="_") + "/daily/" + start + "/" + end)
    req = Request(url, headers={
        "User-Agent": "INTERSECTION-AggregateProductResearch/1.0 (https://koith.github.io/browser-app-lab/apps/demand-research/consumer/)",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    with urlopen(req, timeout=25) as res:
        if res.status != 200 or res.geturl() != url:
            raise ValueError("Wikimedia API changed endpoint or redirected")
        body = res.read(MAX_BODY + 1)
    if not body or len(body) > MAX_BODY:
        raise ValueError("Wikimedia response outside expected size")
    try:
        return json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Wikimedia JSON body") from exc


def process(results: dict[str, dict], *, as_of: str) -> dict:
    """Validate 6 exact per-day time series, return aggregate-only statistics."""
    try:
        checked = date.fromisoformat(as_of)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid as-of date") from exc
    # Allow publication delay so dashboards never show partial current days.
    end = checked - timedelta(days=3)
    days = _day_values(end)
    if set(results) != {a[2] for a in ARTICLES}:
        raise ValueError("exact six allowlisted topics required")
    topics = []
    for key, name, article, kind in ARTICLES:
        payload = results[article]
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("missing Wikimedia article series")
        values: dict[str, int] = {}
        for item in payload["items"]:
            if not isinstance(item, dict) or any(item.get(k) != v for k,v in (
                ("project",PROJECT),("article",article),("access","all-access"),
                ("agent","user"),("granularity","daily"))):
                raise ValueError("unexpected Wikimedia pageview shape")
            stamp = item.get("timestamp")
            count = item.get("views")
            if (not isinstance(stamp, str) or len(stamp) != 10 or
                not stamp.endswith("00") or stamp[:8] not in days or
                not isinstance(count, int) or isinstance(count, bool) or
                not 0 <= count <= MAX_DAY_VIEWS or stamp[:8] in values):
                raise ValueError("duplicate, missing or invalid daily pageview")
            values[stamp[:8]] = count
        if len(values) != 14 or any(day not in values for day in days):
            raise ValueError("incomplete Wikimedia two-week comparison window")
        daily = [{"day": f"{d[:4]}-{d[4:6]}-{d[6:]}", "views": values[d]} for d in days]
        prev = sum(values[d] for d in days[:7])
        current = sum(values[d] for d in days[7:])
        change = round(100 * (current - prev) / prev, 2) if prev else None
        topics.append({
            "id": key, "title": name, "article": article, "article_type": kind,
            "wiki_url": "https://en.wikipedia.org/wiki/" + quote(article, safe="_"),
            "previous_7d_views": prev, "latest_7d_views": current,
            "difference_views": current - prev, "week_on_week_change_pct": change,
            "daily": daily,
        })
    return {
        "schema_version": 1,
        "dataset": {
            "name": "Wikimedia Analytics public Wikipedia article pageviews",
            "kind": "current_article_attention_not_demand",
            "license": "CC0 1.0", "source_url": DOC_URL,
            "project": PROJECT, "access": "all-access", "agent": "user",
            "as_of": as_of, "window_start": topics[0]["daily"][0]["day"],
            "window_end": topics[0]["daily"][-1]["day"],
            "real_aggregate_data": True, "is_purchases": False,
            "is_demand": False, "contains_individuals": False,
            "existing_sns_pipeline_connected": False,
        },
        "summary": {
            "topics": len(topics), "days_per_topic": 14,
            "latest_7d_total_views_across_mixed_topics": sum(t["latest_7d_views"] for t in topics),
        },
        "topics": topics,
        "warnings": [
            "Wikipedia pageviews are encyclopedia attention, not purchase intent, sales, unique readers, or consumer needs.",
            "Article titles mix specific devices and broad categories; totals are not a comparable product ranking.",
            "Bot filtering is imperfect; topical news, browsing, and editorial factors affect traffic.",
            "Counts are in English Wikipedia and the selected articles only, not global web search.",
        ]
    }


def save(report: dict, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, output)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    checked = date.fromisoformat(args.as_of)
    bounds = _day_values(checked - timedelta(days=3))
    results = {}
    for i,(_, _, article, _) in enumerate(ARTICLES):
        if i:
            time.sleep(0.45)
        results[article] = fetch(article, bounds[0], bounds[-1])
    report = process(results, as_of=args.as_of)
    save(report, args.output)
    print(json.dumps({"as_of":args.as_of,"articles":len(report["topics"]),
        "latest_7d_views":report["summary"]["latest_7d_total_views_across_mixed_topics"]}))


if __name__ == "__main__":
    main()
