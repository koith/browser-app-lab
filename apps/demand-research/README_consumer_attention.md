# INTERSECTION — Current public Wikipedia product attention (not demand)

## License, source and semantic boundary

Source: Wikimedia Analytics API (per-article, English Wikipedia, all-access, user agent class).
API documentation and policy: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html
License: CC0 1.0. The public article links are also shown on the dashboard.
Data as-of: 2026-11-03 (UTC). Last complete analyzed day: 2026-10-31.
This report has six allowlisted public Wikipedia product or product-category articles and their 14 exact daily aggregate counts, comparing the last completed 7 days against the prior 7.

It is real **public encyclopedia article attention**, not real consumer sales, product purchases, purchase intention, demand, unique people, specific customer reviews or profile activity. No usernames, account networks, individual sessions or cross-platform correlation are processed.

The chosen article scopes are heterogeneous: PlayStation 5 and Nintendo Switch 2 are device pages; AirPods Pro is a product family; robotic vacuum, espresso machines and standing desks are broad categories. **Never interpret their absolute pageviews as a fair product sales ranking.** News, Wikipedia editing, visitors' curiosity and page title changes may affect counts.

## Important data-quality fix

An initial robot vacuum query used the Wikipedia redirect title Robot_vacuum_cleaner, producing only 7 weekly views. The real canonical English Wikipedia page is Robotic_vacuum_cleaner; the corrected report has 497 last-week views in the 2026-10-25 to 2026-10-31 period. CI tests now lock the canonical name to prevent recurrence.

## Public endpoints

Dashboard: https://koith.github.io/browser-app-lab/apps/demand-research/consumer/

Static read-only aggregate: https://koith.github.io/browser-app-lab/apps/demand-research/consumer/attention-report.json

The separate consumer_report_api.py also includes GET /api/consumer/attention for future isolated hosting, but no new service is provisioned. GitHub Pages is sufficient for current aggregate distribution without new cost.

## Rebuild, QA and refresh

From apps/demand-research:

    python -m pytest -q test_consumer_attention.py test_consumer_sessions.py test_consumer_report.py
    python consumer_attention.py --as-of 2026-11-03 --output consumer/attention-report.json

Source is restricted to six reviewed canonical titles. Fetches are serial (0.45 seconds apart) with an identifying User-Agent URL. JSON schema and fourteen consecutive dates must match, otherwise no report is written. A missing date or failed network call does not become zero activity.

The source API may impose further limits or change availability; CI fails visibly rather than asserting a fabricated number.

Weekly schedule .github/workflows/consumer-attention-weekly.yml checks the six public articles on Monday at 04:29 UTC. A real changed period is staged on a fresh GitHub branch and proposed as a PR for review; **no silent automatic merges or overwrites**. An unavailable API, a regression in dates, or a different topic count fails the job and preserves the last published aggregate.

Privacy note: all data are site-wide pageview totals already published by Wikimedia, no individual or SNS content. The existing anonymous/sensitive SNS pipeline remains disconnected.
