"""Consent-safe, content-level consumer review de-duplication.

Input contract: approved, non-sensitive consumer product reviews or synthetic
fixtures ONLY. No SNS access, image processing, author linkage, or persistence.

An account is a platform-scoped label, never a confirmed natural person.
Exact identical review text is one *content pattern*, NOT one customer.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from hashlib import sha256
from typing import Iterable, Mapping
import re
import unicodedata

MAX_ROWS = 50_000
MAX_TEXT = 5_000
MAX_PRODUCT = 100
KINDS = {"original", "repost", "quote"}


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _day(value: object) -> str:
    if not isinstance(value, str) or len(value) < 10:
        return "unknown"
    day = value[:10]
    try:
        return date.fromisoformat(day).isoformat()
    except ValueError:
        return "unknown"


def analyze(reviews: Iterable[Mapping], *, daily_account_cap: int = 2) -> dict:
    """Aggregate approved consumer reviews. Never asserts common human identity.

    Required: product, platform, post_id.
    Optional: account, posted_at, text, kind=original, repost_of.
    'repost' requires a nonempty repost_of and is counted as amplification.
    A 'quote' is a separate opinion only if it has its own nonempty text.

    Content-level exact duplicates use NFKC/casefold/whitespace normalization.
    No approximate matching (which could merge contradictory opinions).
    """
    if not isinstance(daily_account_cap, int) or not 1 <= daily_account_cap <= 100:
        raise ValueError("daily_account_cap must be 1..100")
    if isinstance(reviews, (str, bytes, Mapping)):
        raise TypeError("reviews must be an iterable of review objects")

    state: dict[str, dict] = {}
    seen_posts: set[tuple[str, str]] = set()
    row_count = 0

    def state_for(product: str) -> dict:
        if product not in state:
            state[product] = {
                "counts": Counter(),
                "exact": set(),
                "accounts": set(),
                "per_account": Counter(),
                "cap_counts": Counter(),
            }
        return state[product]

    for row in reviews:
        row_count += 1
        if row_count > MAX_ROWS:
            raise ValueError("too many reviews in one batch")
        if not isinstance(row, Mapping):
            raise TypeError("every review must be a mapping")
        product = row.get("product")
        platform = row.get("platform")
        post_id = row.get("post_id")
        if not isinstance(product, str) or not 1 <= len(product.strip()) <= MAX_PRODUCT:
            raise ValueError("missing/invalid product")
        if not isinstance(platform, str) or not re.fullmatch(r"[a-z0-9_-]{1,32}", platform):
            raise ValueError("missing/invalid platform")
        if not isinstance(post_id, str) or not 1 <= len(post_id) <= 200:
            raise ValueError("missing/invalid post_id")
        product = product.strip()
        counts = (s := state_for(product))["counts"]
        counts["raw_rows"] += 1

        post_key = (platform, post_id)
        if post_key in seen_posts:
            counts["duplicate_feed_rows"] += 1
            continue
        seen_posts.add(post_key)
        counts["unique_source_posts"] += 1

        kind = row.get("kind", "original")
        if kind not in KINDS:
            raise ValueError("invalid kind")
        if kind == "repost":
            if isinstance(row.get("repost_of"), str) and row["repost_of"].strip():
                counts["reposts"] += 1
            else:
                counts["unknown"] += 1
            continue

        raw_text = row.get("text")
        if isinstance(raw_text, str) and len(raw_text) > MAX_TEXT:
            raise ValueError("text too long")
        normalized = _text(raw_text)
        if not normalized:
            counts["unknown"] += 1
            continue

        counts["text_observations"] += 1
        account = row.get("account")
        if isinstance(account, str) and 0 < len(account) <= 200:
            account_key = (platform, account)
            s["accounts"].add(account_key)
            s["per_account"][account_key] += 1
        else:
            account_key = None
            counts["unknown_account_rows"] += 1

        digest = sha256(normalized.encode("utf-8")).digest()
        if digest in s["exact"]:
            counts["exact_repeat_posts"] += 1
            continue
        s["exact"].add(digest)
        counts["unique_text_patterns"] += 1
        if account_key is None:
            counts["uncapped_unknown_account_patterns"] += 1
        else:
            cap_key = (account_key, _day(row.get("posted_at")))
            if s["cap_counts"][cap_key] < daily_account_cap:
                s["cap_counts"][cap_key] += 1
                counts["account_capped_patterns"] += 1
            else:
                counts["account_cap_excess"] += 1

    products = []
    for product, s in sorted(state.items(), key=lambda x: x[0]):
        c = s["counts"]
        per_account = s["per_account"]
        observations = c["text_observations"]
        products.append({
            "product": product,
            **{key: int(c[key]) for key in (
                "raw_rows", "unique_source_posts", "duplicate_feed_rows",
                "reposts", "text_observations", "unique_text_patterns",
                "exact_repeat_posts", "unknown", "unknown_account_rows",
                "account_capped_patterns", "account_cap_excess",
                "uncapped_unknown_account_patterns"
            )},
            "observed_accounts": len(s["accounts"]),
            "top_account_share": (
                round(max(per_account.values()) / observations, 6)
                if observations and per_account else None
            ),
            "analyzable_text_ratio": (
                round(observations / c["unique_source_posts"], 6)
                if c["unique_source_posts"] else None
            ),
        })
    return {
        "schema_version": 1,
        "input_rows": row_count,
        "products": products,
        "notes": {
            "unique_text_patterns": "Distinct exact-normalized content, NOT distinct people or consumers",
            "account_capped_patterns": "Sensitivity indicator; not an estimate of people",
            "unknown": "Unanalyzable or unverified repost content, never assumed to be unique",
            "reposts": "Amplification separately counted; not an independent review",
        },
    }
