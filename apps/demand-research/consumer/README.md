# INTERSECTION — General Product Evidence / 일반 상품 수요 교차검증

Independent, read-only, general-consumer product evidence workflow. This is **not**
the existing adult/anonymous-social account analysis or content collection module.

## Deployment components

- `../consumer_dedup.py` — pure, standard-library repeat-content
  and contribution concentration metrics. **No person matching or audience identification.**
- `../consumer_report.py` — reproducible synthetic fixtures, and
  separately reviewed first-party/licensed ordinary goods review data, processed
  offline into an **aggregate-only** JSON report.
- `../consumer_report_api.py` — independent FastAPI
  read-only API; never imported by the existing SNS gateway.
- `index.html` — static, responsive report dashboard.
- `demo-report.json` — synthetic-only aggregate output, generated
  from the deterministic fixture. **This is an example, not measured demand.**
- `../../../../.github/workflows/consumer-evidence-qa.yml` —
  unit tests, UI syntax QA and reproducible report generation check.

Public static location after Pages deployment:
`https://koith.github.io/browser-app-lab/apps/demand-research/consumer/`.

The root INTERSECTION page includes only an **ordinary link** to this page;
it does not send existing SNS posts or accounts to the new analyzer.

## Safe synthetic report

```sh
cd apps/demand-research
python consumer_report.py --demo --output consumer/demo-report.json
python -m pytest -q test_consumer_dedup.py test_consumer_report.py
```

The synthetic fixture contains 282 input rows, 280 unique post IDs,
4 products, 68 evidence-supported repeated-content observations,
200 known-content groups, 12 unresolved groups and 43 **observed platform
accounts, not people**. These counts must not be promoted as live market figures.

## Separate, authorized first-party review export

No live SNS API, search crawler, or existing account index is an accepted data source.

1. A reviewer first examines a lawful, owned/licensed dataset of ordinary product
   reviews, independent of this code. This project does not automatically
   assess safety, rights, age or consent.
2. Prepare UTF-8 JSON containing *only*:
   `schema_version: 1`, `source` and `rows`.
   Each row includes only `product_id`, `platform`,
   `author_id`, `post_id`, `text`,
   optional `posted_at`, and optional `repost_of`.
   Do not include profile URLs, images, attachments, birth dates or contact details.
3. The `source` object must have `type` set to
   `first_party_general_product_reviews` or
   `licensed_general_product_reviews`,
   `license` set to `owned` or `licensed`,
   and non-empty `name`, `owner`, `reviewed_by`
   and ISO `reviewed_at` fields.
4. Compute an exact SHA-256 of the **reviewed bytes** before processing.
   A matching digest is an integrity check, **not** proof of review or legality.
5. Run offline; choose a distinct output path to prevent source overwriting:

```sh
sha256sum safe-owned-reviews.json
python consumer_report.py \
  --input safe-owned-reviews.json \
  --approved-sha256 YOUR_64_CHARACTER_HEX_DIGEST \
  --output safe-owned-aggregates.json
```

The output does not store raw product review text or raw account IDs. It does
include aggregate counts, generic product names, and hashed evidence IDs.

### Optional authenticated, independent API

```sh
export CONSUMER_REPORT_MODE=reviewed
export CONSUMER_REPORT_PATH=/private/safe-owned-aggregates.json
export CONSUMER_REPORT_READ_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
uvicorn consumer_report_api:app --host 127.0.0.1 --port 8877
```

Read-only routes:

- `GET /api/consumer/status`
- `GET /api/consumer/summary`
- `GET /api/consumer/products/{product_id}`

Reviewed mode requires the independent `Authorization: Bearer ...`
header. There are no upload or write endpoints. Do not place the bearer token
in GitHub Pages, query parameters, or browser storage. **This API is not deployed
in the public GitHub Pages environment.**

The standalone HTML dashboard instead accepts an **aggregate-only report file**
through an in-browser file picker; it does not upload files. The browser does
not authenticate the provenance of arbitrary selected report files and labels
them accordingly.

## Interpretation / known limitations

- **Raw post count:** unique provider post IDs, not unique humans.
- **Content groups:** connected components of explicit in-fixture repost
  references and exact substantial normalized text matches. **Not a validated
  number of independent customers.** Two separate customers may coincidentally
  write identical text; a missing original may hide a duplicate.
- **Unknown:** missing/short text and unresolved source edges are kept distinct.
  Do not present a lack of evidence as proof of independence.
- **Concentration:** HHI, top account share, and one contribution per platform
  account per known day; no cross-platform deduplication of anonymous people.
- **Coverage:** only the admitted input. Missing sources and platforms are not
  a zero-demand result.
- **Demo vs live:** `is_real_data` and `mode` are
  mandatory flags; the demo is not a live SNS or commerce-demand measurement.
- **Sensitive content:** this workflow must not be supplied with the existing
  adult/anonymous/social feed corpus, sexually explicit media, or any exploitation
  material; no image fingerprint or identity matching component exists.
