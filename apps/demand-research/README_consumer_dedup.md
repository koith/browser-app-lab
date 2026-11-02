# Synthetic general-product review deduplication (isolated proof of concept)

`consumer_dedup.py` is an independent Python standard-library module. It is **not** imported by `gateway.py`, account grouping, public social collection or any scheduled job. It makes no requests and persists nothing.

The only accepted dataset flag is `dataset_kind="synthetic_general_products"`. This flag is a contract for fixture-only use, **not** an automated safety verification mechanism. For now, do not enable live API access, sensitive source ingestion, or production UI wiring.

## Run tests

```sh
cd apps/demand-research
python -m pytest -q test_consumer_dedup.py
```

## API example

```python
from consumer_dedup import analyze
results = analyze([
    {"platform":"fixture","post_id":"1","author_id":"a","product_id":"coffee",
     "text":"I bought this coffee and its rich balanced taste was excellent!",
     "posted_at":"2026-11-02"},
    {"platform":"fixture","post_id":"2","author_id":"b","product_id":"coffee",
     "text":"", "repost_of":"fixture:1", "posted_at":"2026-11-02"},
], dataset_kind="synthetic_general_products")
assert results["products"]["coffee"]["content_groups"] == 1
```

## Metric semantics

- `raw_input_rows`: all input rows, including repeated ingestion.
- `distinct_post_ids`: deduplicated by exact platform and post ID; conflicting reused IDs are rejected.
- `observed_posts`: unique post IDs within the specified product.
- `content_groups`: groups formed by verified, in-input repost links and byte-independent normalized exact **substantial** text matches; unknown texts form separate unresolved groups, **not** certified independent opinions.
- `known_content_groups` / `unresolved_content_groups`: keep evidence quality visible.
- `removed_repeated_content_posts`: `observed_posts - content_groups`; not a count of duplicate humans.
- `verified_repost_edges`: explicitly provided repost links resolving to an existing post in this fixture (not externally authenticated).
- `top_account_share` and `account_hhi`: activity concentration by **platform account only**. They do not establish common ownership.
- `per_account_day_capped_mentions`: one maximum per known platform account per calendar day; unknown days each contribute one rather than silently collapsing.

No fuzzy text matching, image fingerprints, audience identification, inferred account ownership, demographic inference, or live-feed content is implemented. Identical short phrases are deliberately left unresolved. Product-specific aggregation avoids accidental cross-product mergers. This baseline measures repeat content and contribution concentration, not unique customers or independent purchase intent.

Before any real general consumer review data is connected, implement a genuinely separate, inspected/authorized data source and a safety gate appropriate to the source. The dataset flag by itself provides no safety screening.
