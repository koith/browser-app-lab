# INTERSECTION General Product Evidence — independent subsystem

This subsystem deliberately operates on general consumer product review datasets. It does not import or fetch the existing social_sources.py, account_index.py, account_groups.py, private catalog, or the anonymous SNS corpus. The original INTERSECTION feed stays unchanged.

## Implemented

- consumer_dedup.py — repeated source post IDs, explicit repost links, substantial identical text clustering, unresolved data, activity concentration and capped account/day metrics. Evidence IDs are opaque hashes of post keys, **not identities of people**.
- consumer_report.py — reproducible synthetic general consumer goods report, or prior-reviewed first-party/appropriately licensed product review input with exact preapproved SHA-256 admission. Exports only aggregate metrics and opaque evidence IDs; no review text or account names.
- consumer_report_api.py — independent read-only API with public synthetic demo mode or a separately authenticated reviewed-report mode. Does not use the existing gateway.
- consumer/index.html — mobile-friendly Korean ranking dashboard, original versus deduplicated counts, expand-to-see evidence, local JSON report open, CSV export. No file uploaded by the web page.
- Original index.html — safe navigation link to general product evidence lab.

## Public URL

https://koith.github.io/browser-app-lab/apps/demand-research/consumer/

Its checked-in demo-report.json is deterministic synthetic data. It is not actual demand or actual SNS activity.

## Run tests, demo generator, read-only API

From apps/demand-research:

    python -m pytest -q test_consumer_dedup.py test_consumer_report.py
    python consumer_report.py --demo --output consumer/demo-report.json
    CONSUMER_REPORT_MODE=demo uvicorn consumer_report_api:app --host 127.0.0.1 --port 8771

Inspect the API at http://127.0.0.1:8771/api/consumer/summary.

## Prior-reviewed general product data ingestion

The importer accepts an existing JSON file with schema_version=1, source metadata (type, license, name, owner, reviewed_by, reviewed_at), and a rows list. A review row contains only product_id, platform, author_id, post_id, text, posted_at, and optional repost_of. No media or additional account data is permitted.

Permitted source types: first_party_general_product_reviews or licensed_general_product_reviews. License flag: owned or licensed.

A trusted reviewer must vet the source **before** use and provide the SHA-256 for the exact approved file. A digest and metadata do not independently prove safety or ownership. Never use the existing SNS corpus.

    sha256sum ./approved-general-products.json
    python consumer_report.py --input ./approved-general-products.json --approved-sha256 ACTUAL_PREAPPROVED_SHA256 --output ./private-aggregate.json

Only aggregate report output is written. The raw JSON is never committed by this pipeline.

To serve an approved aggregate (separate deployment; not yet production-hosted):

    CONSUMER_REPORT_MODE=reviewed CONSUMER_REPORT_PATH=/private/aggregate.json CONSUMER_REPORT_READ_TOKEN=LONG_RANDOM_SECRET uvicorn consumer_report_api:app --host 127.0.0.1 --port 8771

Reviewed mode fails closed if the path or high-entropy read token is missing; requests require Authorization: Bearer token. Never include tokens in GitHub Pages scripts or URLs.

## Metric semantics

- observed_posts — unique post IDs, not people or purchases.
- content_groups — substantial identical-text or explicitly repost-linked groups; group counts are not independent customers.
- known_content_groups — groups containing substantive text.
- unresolved_content_groups — insufficient evidence; must not be automatically counted as verified independent opinions.
- repeated_content_posts — repeated observations merged by directly supported content evidence.
- top_account_share / account_hhi — concentration by platform account, not cross-platform owner.
- per_account_day_capped_mentions — diagnostic cap, not an estimate of human buyers.
- repeated_groups — up to 30 highest-volume groups per product with opaque evidence post-ID hashes.

## Remaining external dependencies

Actual first-party general review input and verified rights, production API hosting with persistent private aggregate file and HTTPS, and real-world evaluation on approved labeled data are not established by this code. No live SNS ingestion, inferred anonymous identity connection, fuzzy text/media fingerprint matching, or real consumer-demand estimate is claimed.

A source approval manifest is an **administrative admission check**, not an automatic safety/legality classifier. Do not treat a SHA match as permission to analyze otherwise unsuitable content.
