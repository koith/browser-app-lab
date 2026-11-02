"""Privacy-minimal historical shopping session conversion aggregates.

UCI Online Shoppers Purchasing Intention Dataset (Sakar & Kastro, 2018),
DOI: 10.24432/C5F88Q, CC BY 4.0. Exactly 12,330 historical sessions, 1,908
purchase-positive sessions. These are not current transactions or SKU demand.
No individual user, cross-platform account, raw session or inference is exported.

Only the official UCI zip is fetched; CSV is parsed in memory and never stored.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import csv
from datetime import date
from io import BytesIO, StringIO
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile

UCI_URL = "https://archive.ics.uci.edu/static/public/468/online%2Bshoppers%2Bpurchasing%2Bintention%2Bdataset.zip"
UCI_PAGE = "https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset"
DOI = "10.24432/C5F88Q"
LICENSE = "CC BY 4.0"
MAX_ZIP_BYTES = 3_000_000
MAX_CSV_BYTES = 3_000_000
ORIGINAL_SESSIONS = 12_330
ORIGINAL_PURCHASES = 1_908
EXPECTED_COLUMNS = [
    "Administrative", "Administrative_Duration", "Informational",
    "Informational_Duration", "ProductRelated", "ProductRelated_Duration",
    "BounceRates", "ExitRates", "PageValues", "SpecialDay", "Month",
    "OperatingSystems", "Browser", "Region", "TrafficType",
    "VisitorType", "Weekend", "Revenue"
]
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "June", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
VISITORS = ("New_Visitor", "Returning_Visitor", "Other")


def download_zip() -> bytes:
    req = Request(UCI_URL, headers={
        "User-Agent": "INTERSECTION-General-Commerce-OpenData/1.0",
        "Accept": "application/zip,application/octet-stream",
        "Accept-Encoding": "identity",
    })
    with urlopen(req, timeout=35) as response:
        if response.status != 200:
            raise ValueError("official UCI source did not return 200")
        # UCI's own archive host is the only permitted destination.
        if response.geturl().split("/")[2].lower() != "archive.ics.uci.edu":
            raise ValueError("unexpected UCI download redirect")
        data = response.read(MAX_ZIP_BYTES + 1)
    if not data or len(data) > MAX_ZIP_BYTES:
        raise ValueError("UCI zip missing or unexpectedly large")
    return data


def zip_csv(raw: bytes) -> bytes:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ZIP_BYTES:
        raise ValueError("invalid UCI zip size")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            names = [item for item in archive.infolist()
                     if item.filename.split("/")[-1].lower() == "online_shoppers_intention.csv"]
            if len(names) != 1 or names[0].file_size > MAX_CSV_BYTES:
                raise ValueError("missing or oversized official CSV member")
            data = archive.read(names[0])
    except (BadZipFile, RuntimeError) as exc:
        raise ValueError("UCI zip failed integrity check") from exc
    if len(data) > MAX_CSV_BYTES:
        raise ValueError("unexpected uncompressed CSV size")
    return data


def _bool(raw: str, field: str) -> bool:
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    raise ValueError("invalid " + field)


def _bucket(pages: int) -> str:
    if pages == 0:
        return "0"
    if pages <= 5:
        return "1–5"
    if pages <= 15:
        return "6–15"
    if pages <= 40:
        return "16–40"
    return "41+"


def _wilson(purchased: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    p = purchased / total
    d = 1 + z * z / total
    middle = (p + z * z / (2 * total)) / d
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / d
    return [round(100 * max(0, middle - radius), 3),
            round(100 * min(1, middle + radius), 3)]


def _metric(totals: dict, name: str) -> dict:
    n, buys = totals["sessions"], totals["purchases"]
    return {"id": name, "sessions": n, "purchases": buys,
            "conversion_pct": round(100 * buys / n, 3) if n else None,
            "wilson_95_pct": _wilson(buys, n),
            "minimum_group_size_met": n >= 30}


def analyze_csv(csv_bytes: bytes, *, strict_original: bool = True,
                snapshot_date: str = "2026-11-03") -> dict:
    """Produce aggregate-only stats from an inspected UCI source, no row export."""
    date.fromisoformat(snapshot_date)
    if not isinstance(csv_bytes, bytes) or not csv_bytes or len(csv_bytes) > MAX_CSV_BYTES:
        raise ValueError("CSV source size invalid")
    try:
        reader = csv.DictReader(StringIO(csv_bytes.decode("utf-8-sig"), newline=""))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("CSV encoding invalid") from exc
    if reader.fieldnames != EXPECTED_COLUMNS:
        raise ValueError("unexpected UCI shopping CSV schema")
    groupings: dict[str, dict[str, dict]] = {
        group: defaultdict(lambda: {"sessions": 0, "purchases": 0})
        for group in ("month", "visitor", "weekend", "product_pages")
    }
    sessions = 0
    purchases = 0
    for raw in reader:
        if None in raw or any(v is None for v in raw.values()):
            raise ValueError("malformed session row")
        if sessions >= 20_000:
            raise ValueError("excessive session rows")
        month = raw["Month"]
        visitor = raw["VisitorType"]
        if month not in MONTHS or visitor not in VISITORS:
            raise ValueError("unexpected visitor category or month")
        weekend = _bool(raw["Weekend"], "Weekend")
        purchased = _bool(raw["Revenue"], "Revenue")
        try:
            page_count = int(raw["ProductRelated"])
            duration = float(raw["ProductRelated_Duration"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid shopping session numeric feature") from exc
        if page_count < 0 or page_count > 10_000 or not math.isfinite(duration) or duration < 0:
            raise ValueError("out-of-range session feature")
        labels = {
            "month": month,
            "visitor": visitor,
            "weekend": "Weekend" if weekend else "Weekday",
            "product_pages": _bucket(page_count),
        }
        for group, label in labels.items():
            m = groupings[group][label]
            m["sessions"] += 1
            m["purchases"] += int(purchased)
        sessions += 1
        purchases += int(purchased)
    if not sessions:
        raise ValueError("empty source")
    if strict_original and (sessions, purchases) != (ORIGINAL_SESSIONS, ORIGINAL_PURCHASES):
        raise ValueError("official historical dataset changed unexpectedly")
    orders = {
        "month": MONTHS, "visitor": VISITORS,
        "weekend": ("Weekday", "Weekend"),
        "product_pages": ("0", "1–5", "6–15", "16–40", "41+"),
    }
    segments = {}
    for key, order in orders.items():
        segments[key] = [_metric(groupings[key][k], k)
                         for k in order if groupings[key][k]["sessions"]]
        assert sum(m["sessions"] for m in segments[key]) == sessions
        assert sum(m["purchases"] for m in segments[key]) == purchases
    return {
        "schema_version": 1,
        "dataset": {
            "kind": "historical_real_ecommerce_sessions",
            "name": "UCI Online Shoppers Purchasing Intention Dataset",
            "source_url": UCI_PAGE,
            "doi": DOI,
            "authors": "C. Sakar & Y. Kastro (2018)",
            "license": LICENSE,
            "study_year": 2018,
            "snapshot_checked": snapshot_date,
            "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "is_real_data": True, "is_current_data": False,
            "is_current_market_demand": False,
            "contains_person_identifiers": False,
            "individual_sessions_exported": False,
            "existing_sns_pipeline_connected": False,
            "unit": "historical website session (not verified individual or product)",
        },
        "summary": _metric({"sessions": sessions, "purchases": purchases}, "all"),
        "segments": segments,
        "warnings": [
            "Historical one-year site sample donated in 2018; not a 2026 conversion rate.",
            "Revenue is a Boolean purchase outcome for a website session, not sales value or product-specific demand.",
            "VisitorType and product-page count describe associations, not causal effects.",
            "Wilson ranges are illustrative binomial intervals and not calibrated to the population sampling design.",
            "Session counts are not verified distinct human purchasers; no people are linked.",
        ],
    }


def write_json(data: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + ".tmp")
    with temp.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, dest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-date", default="2026-11-03")
    args = parser.parse_args(argv)
    zip_bytes = args.input_zip.read_bytes() if args.input_zip else download_zip()
    report = analyze_csv(zip_csv(zip_bytes), strict_original=True,
                         snapshot_date=args.snapshot_date)
    write_json(report, args.output)
    print(json.dumps({"sessions": report["summary"]["sessions"],
                      "purchases": report["summary"]["purchases"],
                      "conversion_pct": report["summary"]["conversion_pct"],
                      "source_sha256": report["dataset"]["csv_sha256"]}))


if __name__ == "__main__":
    main()
