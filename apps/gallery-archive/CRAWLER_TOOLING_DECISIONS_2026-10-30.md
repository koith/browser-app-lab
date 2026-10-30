# Gallery crawler engineering and tool selection — 2026-10-30

Scope: Yui and Mimmi personal photo archives. The only user-facing gallery inventory is **actually stored, SHA-confirmed image files**. Research evidence and links never count as acquired photos.

## Actual bottlenecks observed

- Mimmi PixiBB parsed and HTTP-verified 1,752 public image URL entries in a long GitHub Actions run, but a conflicting `git rebase` failed the publication stage.
- Mimmi Xiutu/CreamSoda separately verified 373 URL entries and likewise failed during `git rebase`.
- Rechecking identical image bytes on every research sweep wasted most image GETs; fetches could take more than an hour.
- Even a successful research commit is **not** proof of a private TeraBox original, a missing-position fill, or a real deployed gallery render.

## Implemented, tested

1. `apps/gallery-archive/commit_crawler_research.py`: keep collected results in memory, fetch current main, merge by exact album identity and SHA without discarding existing research, rebuild derived indexes and retry a racing Git push. Invalid model/source IDs fail closed.
2. `apps/mimmi-gallery/collect_pixibb_public.py`: reuse prior SHA-checked URLs and re-fetch a rotating 5% daily to catch changed image bytes. Report `fresh_http_verified` independently of `cached_previous_sha_checks`.
3. `apps/mimmi-gallery/collect_xiutu_public.py`: the same SHA evidence cache with truthful historical/fresh counts.
4. `apps/gallery-archive/public_crawl_transport.py`: `requests` connection pooling and bounded transient 429/5xx retry; respect `Retry-After`. Never retry 401/403/451 as a bypass.
5. Two live research workflows and their QA workflow now use selective Git checkout, avoiding unrelated source modules/media.
6. `gallery-crawler-efficiency-qa.yml`: tests conflict merge, cache accuracy, retry boundaries and estimated avoided image requests against actual research manifests.
7. Cloud upload remains the only place that certifies original bytes. Final completion additionally requires the deployed GitHub Pages gallery mobile/browser thumbnail, original and refresh QA.

## Further tools evaluated

| Tool | Good fit | Decision |
| --- | --- | --- |
| **gallery-dl** | Public albums on natively supported social/photo platforms, including resume and download archives | Optional future public-SNS adapter after confirming each supported extractor; never assume site support or use a login/paywall workaround |
| **Crawlee for Python** | Request queue, duplicate URL management, bounded retry and Playwright-based multi-page/JS work | Consider for a new long-running discovery source; the existing PixiBB and Xiutu parsers already handle their normal published pages |
| **Scrapy** | Larger-scale normal public HTML crawls with AutoThrottle, HTTP cache and crawl persistence | Consider when the source count grows enough to justify a separate worker |
| **Direct requests + BeautifulSoup** | Already-rendered public HTML and original image byte validation | Keep as the fast path for known PixiBB and Xiutu source pages |
| **Playwright** | Script-rendered content, ordinary lazy loading and infinite scroll | Continue only where static HTML misses real public images; costly on every page |

Do not substitute any alternative tool for physical SHA/image verification. Do not broaden access through paid endpoints, passwords, anti-bot evasion, fabricated numbered image URLs, proxy rotation or third-party cookie sharing.

## Measure and report

- `research_discovered`: unique URLs with validated SHA evidence, **not saved**.
- `cached_previous_sha_checks`: historical research evidence reused to avoid HTTP GETs.
- `fresh_http_verified`: source image bytes actually read and hashed in this crawl.
- `new_private_originals`: distinct physical files newly persisted and re-read from TeraBox.
- `gallery_visible`: the resulting actual deployed gallery rows with live thumbnail and original-browser checks.

This file is an engineering record, not a statement that all historical paid photobooks have been recovered.
