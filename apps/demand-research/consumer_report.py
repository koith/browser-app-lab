"""Independent general-product review report builder.

Only deterministic synthetic fixtures OR separately reviewed first-party/owned
general-product datasets with exact SHA-256 admission. No SNS adapters, no
network requests, no raw-text retention, no account-person inference.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from consumer_dedup import DATASET_KIND, _analyze_rows

SCHEMA_VERSION = 1
MAX_BYTES = 8_000_000
ALLOWED_SOURCE_TYPES = {"first_party_general_product_reviews", "licensed_general_product_reviews"}
ALLOWED_LICENSES = {"owned", "licensed"}
PRODUCTS = {
    "coffee": ("커피", "Fresh roasted coffee aroma has a balanced body and a smooth finish"),
    "earbuds": ("무선 이어폰", "Wireless earbuds sound balanced and the comfortable fit lasts for hours"),
    "sneakers": ("운동화", "These running shoes feel supportive during a long neighborhood walk"),
    "water": ("생수", "This bottled spring water has a refreshing clean and neutral taste"),
}
POST_FIELDS = {"product_id", "platform", "author_id", "post_id", "text", "posted_at", "repost_of"}


def demo_rows() -> list[dict]:
    """Four non-sensitive SKUs with reproducible posts/reposts/exact reuse."""
    rows = []
    for sku, (_, stem) in PRODUCTS.items():
        for i in range(50):
            rows.append({"platform": "demo", "post_id": f"{sku}-{i}",
                "author_id": f"shopper-{i % 23}", "product_id": sku,
                "text": f"{stem}; review sample number {i} with product feedback.",
                "posted_at": f"2026-10-{(i % 28) + 1:02d}"})
        for i in range(10):
            rows.append({"platform": "demo", "post_id": f"{sku}-repost-{i}",
                "author_id": f"republisher-{i}", "product_id": sku, "text": "",
                "repost_of": f"demo:{sku}-{i}", "posted_at": "2026-11-01"})
        for i in range(7):
            rows.append({"platform": "second", "post_id": f"{sku}-repeat-{i}",
                "author_id": f"another-{i}", "product_id": sku,
                "text": f"{stem}; review sample number {i} with product feedback.",
                "posted_at": "2026-11-02"})
        for i in range(3):
            rows.append({"platform": "demo", "post_id": f"{sku}-unknown-{i}",
                "author_id": f"unknown-{i}", "product_id": sku, "text": "",
                "posted_at": ""})
    rows.extend([dict(rows[0]), dict(rows[1])])  # repeated source ingestion
    return rows


def _report(rows: list[dict], *, name: str, dataset_kind: str, digest: str,
            mode: str, provenance: dict) -> dict:
    analysis = _analyze_rows(rows, dataset_kind=dataset_kind, with_groups=True)
    items = []
    for product, metric in analysis["products"].items():
        display = PRODUCTS.get(product, (product,))[0]
        known = metric["known_content_groups"]
        unresolved = metric["unresolved_content_groups"]
        n = metric["observed_posts"]
        items.append({
            "product_id": product, "name": display,
            **metric,
            "duplicate_ratio": round(metric["removed_repeated_content_posts"] / n, 6) if n else 0,
            "evidence_lower_bound": known,
            "unresolved_upper_bound": known + unresolved,
            "quality": "incomplete" if unresolved or metric["missing_repost_targets"] else "observed",
        })
    items.sort(key=lambda p: (-p["known_content_groups"], p["product_id"]))
    summary = {
        "raw_input_rows": analysis["raw_input_rows"],
        "unique_post_ids": analysis["distinct_post_ids"],
        "repeated_ingestion_rows": analysis["repeated_ingestion_rows"],
        "unique_content_groups": sum(p["content_groups"] for p in items),
        "known_content_groups": sum(p["known_content_groups"] for p in items),
        "unresolved_groups": sum(p["unresolved_content_groups"] for p in items),
        "repeated_content_posts": sum(p["removed_repeated_content_posts"] for p in items),
        "observed_accounts_not_people": len({
            (r["platform"], r["author_id"]) for r in rows
        }),
        "products": len(items),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "name": name, "mode": mode, "is_real_data": mode == "reviewed",
            "kind": dataset_kind, "sha256": digest, "provenance": provenance,
            "safe_inputs_only": True, "same_person_inferred": False,
            "existing_sns_pipeline_connected": False,
        },
        "summary": summary,
        "products": items,
        "meaning": {
            "known_content_groups": "근거가 있는 콘텐츠 그룹 수. 고유 소비자 수가 아닙니다.",
            "unresolved_groups": "내용 또는 출처 근거가 부족해 독립성 확인이 어려운 그룹입니다.",
            "repeated_content_posts": "정확한 본문 중복 또는 명시된 재게시 링크로 병합된 게시물입니다.",
        },
    }


def build_demo() -> dict:
    rows = demo_rows()
    serial = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return _report(rows, name="일반 소비재 합성 데이터", dataset_kind=DATASET_KIND,
                   digest=hashlib.sha256(serial).hexdigest(), mode="demo",
                   provenance={"source": "local_deterministic_fixture", "generated": "2026-11-02"})


def build_reviewed(data: bytes, *, approved_sha256: str) -> dict:
    """Convert an *already externally reviewed* local data snapshot to aggregates.

    An exact approved digest prevents accidental data-source swaps. It does NOT
    verify licensing or classify unsafe content. Only a trusted reviewer may
    approve input. Never run this on the existing sensitive SNS corpus.
    """
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError("dataset must be an existing JSON byte string up to 8 MB")
    sha = hashlib.sha256(data).hexdigest()
    if not isinstance(approved_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", approved_sha256):
        raise ValueError("a valid approved sha256 is required")
    if sha != approved_sha256:
        raise ValueError("approved sha256 does not match the source bytes")
    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON input") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid reviewed dataset schema")
    source = payload.get("source")
    if not isinstance(source, dict) or source.get("type") not in ALLOWED_SOURCE_TYPES or source.get("license") not in ALLOWED_LICENSES:
        raise ValueError("source must be an approved first-party or licensed general-product source")
    for key in ("name", "owner", "reviewed_by", "reviewed_at"):
        value = source.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 180:
            raise ValueError(f"missing or invalid source.{key}")
    try:
        datetime.fromisoformat(source["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid source.reviewed_at") from exc
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("reviewed dataset must have nonempty rows")
    for record in rows:
        if not isinstance(record, dict) or not set(record).issubset(POST_FIELDS):
            raise ValueError("unapproved row fields (media and account enrichment excluded)")
    # No raw review content, raw account identifiers, or post URLs are written
    # to the resulting report.
    clean_source = {key: source[key] for key in ("type", "license", "name", "owner", "reviewed_at")}
    return _report(rows, name=source["name"], dataset_kind="reviewed_general_products",
                   digest=sha, mode="reviewed", provenance=clean_source)


def write_report(report: dict, output: Path) -> None:
    """Write aggregates only, never the original review rows."""
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    target = output.with_name(output.name + ".tmp")
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    with target.open("wb") as f:
        f.write(encoded)
        f.flush()
        os.fsync(f.fileno())
    os.replace(target, output)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--demo", action="store_true")
    options.add_argument("--input", type=Path, help="pre-reviewed first-party review JSON")
    parser.add_argument("--approved-sha256", help="approved digest of exact input bytes")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.demo:
        report = build_demo()
    else:
        if not args.approved_sha256:
            parser.error("--approved-sha256 is required for curated input")
        report = build_reviewed(args.input.read_bytes(), approved_sha256=args.approved_sha256)
    write_report(report, args.output)
    print(json.dumps({"output": str(args.output), "demo": not report["dataset"]["is_real_data"],
                      "products": report["summary"]["products"],
                      "unique_posts": report["summary"]["unique_post_ids"]}))


if __name__ == "__main__":
    main()
