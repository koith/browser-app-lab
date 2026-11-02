# Consumer Signal Lab — standalone content-level deduplication

This is a separate, generic prototype for approved, non-sensitive consumer
product reviews and synthetic datasets. It does not import from, call into,
modify, authenticate with, or deploy the existing demand-research SNS collector.
It has no scraper, SNS API, cloud connection, user lookup, image analysis,
cross-account owner inference, database writes, or website UI.

## Why separate?

A repository can include data pipelines with different risk profiles.
Generic data analysis can be tested without opening or processing sensitive
user-generated content. Do not connect this code to a live ingestion flow until
the input data's source, permitted use, sensitivity, and access are separately
reviewed. In particular do not use it on sexual content, suspected exploitation,
minors' sexual material, or to infer who controls anonymous accounts.

## Tested metrics

- raw_rows: all feed rows presented by the caller.
- unique_source_posts: unique exact (platform, post_id) pairs.
- duplicate_feed_rows: repeated retrieval of the same platform post.
- unique_text_patterns: exact normalized nonempty text patterns within a
  product, not unique people, buyers, endorsements or independent authors.
- exact_repeat_posts: observations beyond the first exact text pattern.
- reposts: explicit reposts whose source ID was supplied by the caller.
- unknown: blank text and unverified reposts; not assumed to be unique.
- observed_accounts and top_account_share: account-level concentration,
  not an estimate of distinct humans.
- account_capped_patterns: optional per-account-per-product-per-day cap
  applied to unique text patterns, a sensitivity metric, not a person count.
- analyzable_text_ratio: fraction of source-unique posts with analyzable
  text. Reposts count as amplification rather than independent opinions.

Text normalization uses Unicode NFKC, casefold, and whitespace collapsing.
It does not perform semantic similarity, image hashing, author re-identification,
sentiment classification, or fuzzy merging of potentially conflicting reviews.
Exact text match does not prove accounts have the same owner.

## Run

Requires Python 3.10+ with only the standard library:

    python -m unittest discover -s apps/consumer-signal-lab -p 'test_*.py' -v

Code usage with synthetic, ordinary product review data:

    import sys
    sys.path.insert(0, 'apps/consumer-signal-lab')
    from consumer_signal import analyze

    rows = [
        {'product':'텀블러', 'platform':'sample', 'post_id':'1',
         'account':'demo-a', 'text':'텀블러 세척하기 편해요'},
        {'product':'텀블러', 'platform':'sample', 'post_id':'2',
         'account':'demo-b', 'text':'텀블러 세척하기 편해요'},
    ]
    print(analyze(rows)['products'][0]['unique_text_patterns'])  # 1

## Integration gate / no production effects

Stage 1: pure offline code + deterministic synthetic tests (this PR).

Stage 2 (separate approval): connect only vetted, ordinary consumer review
datasets with explicit source and content restrictions. Exclude unsafe or
ambiguous content at intake; do not build a bypass around a rejected collector.
Validate content accuracy, representativeness, duplicate detection and audit
provenance before interpreting counts as demand.

Stage 3 (separate review): aggregate-only output for dashboards, with
raw vs. deduplicated counts, known gaps, and conservative labeling. No
person-level identity or cross-platform anonymous-account linkage.

The output is a content-pattern analysis; it cannot measure total customers
or correct unseen sampling bias. Synthetic tests do not establish real-world
model validity.
