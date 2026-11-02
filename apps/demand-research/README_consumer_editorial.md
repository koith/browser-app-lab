# INTERSECTION — Published expert product evidence (real, licensed)

## Source and attribution

- Canonical dataset: https://verdict-reviews.com/data/
- Source title: Verdict Cross-Publication Product Review Ratings, Michael Hunter (2026).
- License: CC BY 4.0 https://creativecommons.org/licenses/by/4.0/
- Retrieved source snapshot date: 2026-11-03.
- Full original dataset: 8,107 expert rating rows and 2,169 products.
- Deliberately selected ordinary goods: robot vacuums, wireless earbuds, 4K monitors, coffee grinders, espresso machines, mirrorless cameras, standing desks.
- Subset: 36 products, 146 published review URLs, 101 scores explicitly published by outlets, 8 model-derived scores excluded and 37 unscored review rows.
- The published JSON contains aggregate scores and up to three attribution URLs per product, but no raw article text, SNS posts, people or account profiles.

**Editorial expert ratings are not purchases, consumer demand, unique buyers or current sales.** The website visibly labels this distinction. The conservative average only includes scores directly printed by an outlet. Unscored articles and model-derived scores are separate. Same (product,category,review URL) duplicates are removed; syndicated stories under different URLs may remain duplicated. Publisher labels are not normalized identities.

## Read-only production endpoint and reproducibility

Published static dataset (valid JSON with no key required):
https://koith.github.io/browser-app-lab/apps/demand-research/consumer/editorial-report.json

From apps/demand-research, run:

    python -m pytest -q test_consumer_editorial.py test_consumer_dedup.py test_consumer_report.py
    python consumer_editorial.py --as-of 2026-11-03 --output consumer/editorial-report.json

The importer downloads only two fixed canonical source URLs, enforces HTTPS, no redirects, source size caps, exact CSV field lists, source row floors and the seven-category ordinary product allowlist. Source SHA-256 is recorded. All existing anonymous/social account data pipelines remain **disconnected**.

The public static JSON provides the read-only API for the licensed aggregate. A code-only read-only /api/consumer/editorial endpoint exists in the separate consumer_report_api.py, but we do **not** create another paid or quota-consuming Render service just for open public JSON. Existing live services are not affected.

## Scheduled update process

The consumer-editorial-weekly.yml workflow compares exact canonical source CSV hashes every Monday at 04:23 UTC. If the source changed and coverage remains within guarded bounds, it opens a new reviewable PR; it does not silently update production. Source changes may cause CI snapshot mismatch until a new report is reviewed and approved.

## Further limits

- Original dataset is editorial and does not measure unique customers or demand.
- The seven-category subset is not population-representative.
- A source licence permits use of the released dataset; linked publishers retain their separate rights. Only URLs and derived numerical measures are included here.
- First-party customer review import in consumer_report.py still requires genuine prior source rights/content review and exact SHA-256 admission. A checksum alone is not an automatic safety or rights check.
- Existing adult/anonymous SNS data and potential sensitive content are not admitted to this independent pipeline.
