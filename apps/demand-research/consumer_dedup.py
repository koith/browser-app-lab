"""Independent, stdlib-only deduplication for synthetic general-product reviews.

No network access, no SNS ingestion, no storage, no image processing, and no
cross-platform inference about the human operating an account. The caller must
provide an explicitly admitted dataset kind. This module is deliberately not
connected to INTERSECTION's social source, account, or gateway modules.

A content group represents repeated *content*, not a shared person or even
necessarily a single independent opinion. In particular, generic short reviews
are not merged solely because their text is identical.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import re
import unicodedata
from datetime import date
from typing import Mapping

DATASET_KIND = "synthetic_general_products"
MAX_ROWS = 50000
MAX_TEXT = 8000
MAX_FIELD = 240
MIN_EXACT_CHARS = 24
MIN_EXACT_WORDS = 4


def _field(value: object, name: str, *, optional: bool = False) -> str:
    if optional and (value is None or value == ""):
        return ""
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_FIELD:
        raise ValueError(f"invalid {name}")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"invalid {name}")
    return value.strip()


def _normalise(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)).strip()


def _hashable_text(text: str) -> str | None:
    norm = _normalise(text)
    # Short greetings, generic endorsements and one-word replies are not
    # reliable evidence of content reuse by different accounts.
    if len(norm.replace(" ", "")) < MIN_EXACT_CHARS or len(norm.split()) < MIN_EXACT_WORDS:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _day(value: object) -> str:
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError("invalid posted_at")
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError("invalid posted_at") from exc
    if len(value) > 10 and value[10] not in ("T", " "):
        raise ValueError("invalid posted_at")
    return parsed.isoformat()


class _DSU:
    def __init__(self, items: list[str]):
        self.parent = {x: x for x in items}

    def root(self, key: str) -> str:
        parent = self.parent
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.root(a), self.root(b)
        if ra == rb:
            return False
        if ra > rb:
            ra, rb = rb, ra
        self.parent[rb] = ra
        return True


def analyze(rows: list[Mapping[str, object]], *, dataset_kind: str, with_groups: bool = False) -> dict:
    """Analyze an explicitly synthetic, non-sensitive general-product fixture.

    Each row requires product_id, platform, author_id, post_id, and text. An
    optional repost_of is an exact 'platform:post_id' present in *this input*.
    No persistent account linkage is performed. The dataset-kind gate is an
    interface constraint, NOT an automated content safety classifier.
    """
    if dataset_kind != DATASET_KIND:
        raise ValueError("only the synthetic general-products dataset is supported")
    return _analyze_rows(rows, dataset_kind=DATASET_KIND, with_groups=with_groups)


def _analyze_rows(rows: list[Mapping[str, object]], *, dataset_kind: str,
                  with_groups: bool = False) -> dict:
    """Internal pure grouping implementation. Admission belongs to the caller."""
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("rows must be a list of at most 50000 observations")

    unique: dict[str, dict] = {}
    repeated_ingestion = 0
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("each row must be an object")
        platform = _field(row.get("platform"), "platform")
        post_id = _field(row.get("post_id"), "post_id")
        product = _field(row.get("product_id"), "product_id")
        account = _field(row.get("author_id"), "author_id")
        raw = row.get("text", "")
        if not isinstance(raw, str) or len(raw) > MAX_TEXT:
            raise ValueError("invalid text")
        repost_of = _field(row.get("repost_of"), "repost_of", optional=True)
        day = _day(row.get("posted_at"))
        key = f"{platform}:{post_id}"
        info = dict(key=key, product=product, account=f"{platform}:{account}",
                    text=_hashable_text(raw), repost_of=repost_of, day=day)
        old = unique.get(key)
        if old is not None:
            if old != info:
                raise ValueError(f"conflicting entries for post ID {key}")
            repeated_ingestion += 1
        else:
            unique[key] = info

    by_product: dict[str, list[dict]] = defaultdict(list)
    for info in unique.values():
        by_product[info["product"]].append(info)
    result = {}
    for product, posts in sorted(by_product.items()):
        keys = [p["key"] for p in posts]
        dsu = _DSU(keys)
        exact_index = {}
        exact_links = 0
        repost_links = 0
        unknown_reposts = 0
        missing_text = 0
        missing_day = 0
        account_counts = Counter()
        daily_keys = set()
        for p in posts:
            account_counts[p["account"]] += 1
            if p["day"]:
                daily_keys.add((p["account"], p["day"]))
            else:
                missing_day += 1
            if not p["text"]:
                missing_text += 1
            if p["text"]:
                earlier = exact_index.setdefault(p["text"], p["key"])
                if earlier != p["key"] and dsu.union(p["key"], earlier):
                    exact_links += 1
        for p in posts:
            target = p["repost_of"]
            if not target:
                continue
            original = unique.get(target)
            if original is None:
                unknown_reposts += 1
                continue
            if original["product"] != product:
                raise ValueError("repost target has a conflicting product")
            repost_links += 1
            dsu.union(p["key"], target)

        groups: dict[str, list[dict]] = defaultdict(list)
        for p in posts:
            groups[dsu.root(p["key"])].append(p)
        known_groups = 0
        unresolved_groups = 0
        max_group_size = 0
        repeated_groups = []
        for group in groups.values():
            if with_groups and len(group) > 1:
                keys_in_group = {p["key"] for p in group}
                methods = []
                if any(p["repost_of"] in keys_in_group for p in group if p["repost_of"]):
                    methods.append("explicit_repost")
                text_frequency = Counter(p["text"] for p in group if p["text"])
                if any(n > 1 for n in text_frequency.values()):
                    methods.append("exact_substantial_text")
                digest = hashlib.sha256((product + "\\0" + "\\0".join(sorted(keys_in_group))).encode()).hexdigest()[:12]
                repeated_groups.append({
                    "group_id": "C-" + digest, "posts": len(group),
                    "accounts": len({p["account"] for p in group}),
                    "methods": methods,
                    "evidence_ids": sorted(hashlib.sha256(p["key"].encode()).hexdigest()[:12] for p in group)[:12],
                })
            max_group_size = max(max_group_size, len(group))
            if any(p["text"] for p in group):
                known_groups += 1
            else:
                unresolved_groups += 1
        n = len(posts)
        frequencies = list(account_counts.values())
        result[product] = {
            "observed_posts": n,
            "content_groups": len(groups),
            "known_content_groups": known_groups,
            "unresolved_content_groups": unresolved_groups,
            "removed_repeated_content_posts": n - len(groups),
            "verified_repost_edges": repost_links,
            "exact_text_join_edges": exact_links,
            "missing_repost_targets": unknown_reposts,
            "short_or_missing_text_posts": missing_text,
            "largest_content_group": max_group_size,
            "observed_accounts": len(account_counts),
            "top_account_share": round(max(frequencies) / n, 6),
            "account_hhi": round(sum((v / n) ** 2 for v in frequencies), 6),
            "per_account_day_capped_mentions": len(daily_keys) + missing_day,
            "missing_post_day": missing_day,
        }
        if with_groups:
            result[product]["repeated_groups"] = sorted(
                repeated_groups, key=lambda g: (-g["posts"], g["group_id"]))[:30]
    return {
        "dataset_kind": dataset_kind,
        "raw_input_rows": len(rows),
        "distinct_post_ids": len(unique),
        "repeated_ingestion_rows": repeated_ingestion,
        "human_identity_inferred": False,
        "live_sources_connected": False,
        "products": result,
    }
