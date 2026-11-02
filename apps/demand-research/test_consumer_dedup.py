"""Only synthetic, non-sensitive general consumer goods review fixtures."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from consumer_dedup import DATASET_KIND, analyze


def row(i, *, product="coffee", platform="sample", author=None, text=None,
        repost_of="", day="2026-11-02"):
    return {"platform": platform, "post_id": f"post-{i}",
            "author_id": author or f"customer-{i}", "product_id": product,
            "text": (f"I bought this coffee and the rich balanced taste was excellent, sample {i}"
                     if text is None else text),
            "posted_at": day, "repost_of": repost_of}


def check(rows):
    return analyze(rows, dataset_kind=DATASET_KIND)


def test_ten_explicit_reposts_form_one_content_group():
    origin = row(0)
    posts = [origin] + [row(i, repost_of="sample:post-0", text="") for i in range(1, 10)]
    r = check(posts)["products"]["coffee"]
    assert r["observed_posts"] == 10
    assert r["content_groups"] == r["known_content_groups"] == 1
    assert r["removed_repeated_content_posts"] == 9
    assert r["verified_repost_edges"] == 9
    assert r["observed_accounts"] == 10


def test_ten_independent_reviews_remain_ten_content_groups():
    r = check([row(i) for i in range(10)])["products"]["coffee"]
    assert r["content_groups"] == 10
    assert r["removed_repeated_content_posts"] == 0
    assert r["top_account_share"] == 0.1
    assert r["account_hhi"] == 0.1


def test_exact_substantial_text_reused_across_accounts_and_platforms():
    text = "These wireless earbuds have remarkably clear sound and stable battery life."
    posts = [row(1, product="earbuds", text=text),
             row(2, product="earbuds", platform="other", text=text),
             row(3, product="coffee", text=text)]
    r = check(posts)["products"]
    assert r["earbuds"]["content_groups"] == 1
    assert r["earbuds"]["exact_text_join_edges"] == 1
    assert r["coffee"]["content_groups"] == 1


def test_short_common_reviews_are_not_silently_merged():
    data = [row(i, text="좋아요") for i in range(10)]
    r = check(data)["products"]["coffee"]
    assert r["content_groups"] == 10
    assert r["unresolved_content_groups"] == 10


def test_positive_and_negative_opinions_remain_separate():
    p = row(1, text="I really like these shoes and their comfortable fit and durable materials.")
    n = row(2, text="I really dislike these shoes and their uncomfortable fit and fragile materials.")
    assert check([p, n])["products"]["coffee"]["content_groups"] == 2


def test_unavailable_original_is_unknown_not_a_confirmed_duplicate():
    r = check([row(1, text="", repost_of="other:missing-post")])["products"]["coffee"]
    assert r["missing_repost_targets"] == 1
    assert r["unresolved_content_groups"] == 1
    assert r["removed_repeated_content_posts"] == 0


def test_missing_content_does_not_generate_unique_independent_opinion_claim():
    r = check([row(i, text="") for i in range(3)])["products"]["coffee"]
    assert r["known_content_groups"] == 0
    assert r["unresolved_content_groups"] == 3


def test_duplicate_ingestion_id_does_not_inflate():
    first = row(1)
    r = check([first, dict(first)])
    assert r["raw_input_rows"] == 2
    assert r["distinct_post_ids"] == 1
    assert r["repeated_ingestion_rows"] == 1


def test_conflicting_post_id_and_product_repost_are_rejected():
    with pytest.raises(ValueError, match="conflicting entries"):
        check([row(1), row(1, text="Entirely different opinion")])
    with pytest.raises(ValueError, match="conflicting product"):
        check([row(1), row(2, product="earbuds", repost_of="sample:post-1")])


def test_account_day_cap_is_per_platform_account_not_person():
    a = [row(i, author="one", day="2026-11-02") for i in range(5)]
    b = [row(i + 100, author="one", day="2026-11-03") for i in range(2)]
    r = check(a + b)["products"]["coffee"]
    assert r["observed_accounts"] == 1
    assert r["per_account_day_capped_mentions"] == 2
    assert r["top_account_share"] == 1.0


def test_reject_unapproved_data_connections():
    with pytest.raises(ValueError, match="only the synthetic"):
        analyze([row(1)], dataset_kind="live_social_feed")
    with pytest.raises(ValueError, match="only the synthetic"):
        analyze([row(1)], dataset_kind="verified_general_products")


def test_large_20k_fixture_runs_and_preserves_account_distinction():
    reviews = [row(i, product=f"product-{i % 20}", author=f"account-{i % 1000}")
               for i in range(20000)]
    r = check(reviews)
    assert r["distinct_post_ids"] == 20000
    assert sum(p["observed_posts"] for p in r["products"].values()) == 20000
    assert all(p["removed_repeated_content_posts"] == 0 for p in r["products"].values())
    assert r["human_identity_inferred"] is False
    assert r["live_sources_connected"] is False
