# INTERSECTION — Historical real online shopping conversion evidence

## Direct source, license and scope

- Original data: UCI Online Shoppers Purchasing Intention Dataset.
- Authors: C. Sakar & Y. Kastro; donated in 2018.
- DOI: https://doi.org/10.24432/C5F88Q
- Official landing page: https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset
- License: CC BY 4.0. Attribution and link must remain visible.
- Original source: 12,330 historical e-commerce website sessions, of which 1,908 ended with a purchase (Revenue=True); overall observed conversion is 15.474%.
- The exact collection dates and the identity of the merchant are not inferred. This is NOT a 2026 survey, recent sales tracker, universal market baseline or an account-owner linkage mechanism.
- Source zip and original CSV stay in volatile process memory during the scheduled CI run; only an aggregated JSON is checked in.
- Raw individual session rows, IP addresses, email addresses, browser fingerprints, usernames and purchase item identities are NEVER exported. The original dataset does not establish SKU sales or current market size.

### Production path (public static read-only data)

https://koith.github.io/browser-app-lab/apps/demand-research/consumer/session-report.json

The dashboard https://koith.github.io/browser-app-lab/apps/demand-research/consumer/ has **three explicitly distinguished areas**:

1. Real *historical* e-commerce session purchase completion by month, visitor type, weekday/weekend, and product-page view bucket.
2. Real licensed current published *expert editorial scores* for 36 ordinary consumer products (NOT purchases).
3. Synthetic general-products *content deduplication experiment* (NOT real demand).

They are independent evidence sources with incompatible units and must not be added into one scalar "demand score".

### Implementation and quality checks

- consumer_sessions.py downloads just the single official UCI ZIP URL; enforces host, exact CSV schema, maximum compressed/uncompressed sizes and original 12,330/1,908 integrity counts.
- Unwanted member files in the ZIP are not extracted. Archive is parsed in memory using Python stdlib.
- Aggregations use counts and Wilson 95% descriptive intervals. They do NOT infer person identities, demographic attributes or causal effects.
- Segments with fewer than 30 sessions receive a visible insufficient-sample flag; all segment totals must add back to the same 12,330 sessions and 1,908 purchases.
- consumer/session_view.js shows responsive bars and independent filters. HTML source and numeric accessibility text remain available.
- CI tests the official source, snapshot match and fully hydrated browser DOM. Checkout uses sparse paths for performance.

### Rebuild

From apps/demand-research:

    python -m pytest -q test_consumer_sessions.py test_consumer_dedup.py test_consumer_report.py
    python consumer_sessions.py --snapshot-date 2026-11-03 --output consumer/session-report.json

An additional non-production FastAPI read-only endpoint exists at GET /api/consumer/sessions within consumer_report_api.py. It returns only the bundled aggregate and rejects POST. No extra paid hosting service was provisioned. The published static JSON endpoint is fully functional at GitHub Pages without credentials or recurring infrastructure costs.

### Important interpretation limits

- 15.474% describes **the historical sample** only. It should not be forecast as today's conversion.
- The source describes each row as a session from a particular website, and says the sample construction aimed to avoid repeated-user bias; it is still not an identity-verification dataset.
- Differences between returning vs new visitors, pages viewed and month are observational associations. They do not establish causality; comparisons may be confounded by other variables.
- The "Revenue" outcome denotes a purchase occurring in a session, not the monetary amount, quantity, margin, repeat orders, or individual SKUs.
- A Wilson interval is an illustrative binomial estimate, not a guarantee of representative sampling or prediction accuracy.
- No existing sensitive anonymous SNS or person-matching system is connected.
