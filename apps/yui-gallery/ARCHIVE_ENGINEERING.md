# Image Archive Engineering — verified research (2026-10-26)

## Reusable existing solutions
- gallery-dl: download archives, retry/backoff, request pacing, skip duplicates and full album extractors. https://github.com/mikf/gallery-dl/blob/master/docs/options.md
- Scrapy CrawlSpider: follow all qualified pagination links with explicit request rules. https://docs.scrapy.org/en/latest/topics/spiders.html
- Scrapy Images Pipeline: file downloads, checksums, thumbnails, image size checks and custom storage. https://docs.scrapy.org/en/latest/topics/media-pipeline.html
- Playwright Network: real JS browser, scroll, image network events and dynamically rendered pages. https://playwright.dev/python/docs/network
- NDSA Preservation Levels: integrity/fixity, provenance, independent copies, retrievability. https://www.ndsa.org/activities/levels-of-digital-preservation/
- Immich external libraries: index existing folder-based local/remote-mounted media without rewriting originals. https://docs.immich.app/features/libraries/

## Acceptance pipeline
DISCOVER -> SOURCE/GALLERY ID -> PAGE ENUMERATION -> LAZY IMAGE RESOLUTION -> BEST VARIANT -> REAL FILE DOWNLOAD -> IMAGE DECODE -> SHA256 -> DUPLICATE AUDIT -> INVENTORY COMPARISON -> STORAGE -> GALLERY MOBILE QA.

1. Never equate a collection landing page with a full photobook. Count all pages and dynamic scroll loads.
2. Exclude adverts, related albums, avatars and unrelated models; inspect article/gallery area and per-site image path rules.
3. Preserve source, publication date vs upload date, album name, claimed image count, visited pages, image type (preview/original), image dimensions, bytes, SHA256, original URL and local file path.
4. Record separately advertised count (e.g. 194P), actual publicly visible preview count (e.g. 1), downloaded count and failed count; missing images means PARTIAL not COMPLETE.
5. Use responsive srcset/data-original/data-src lazy-loading values, scripted pagination and infinite scrolling; do not only parse initially loaded HTML.
6. Deduplicate exact byte hashes across sites; mark near-duplicate perceptual matches for review but do not delete distinct poses.
7. Validate with Pillow opening each image, archive CRC/zipfile.testzip and mobile browser QA including image.naturalWidth.
8. Never claim an empty file hierarchy or a list of remote links is an image archive. Re-check physical stored bytes.
9. External storage needs a real connected account and test upload/download. Unconnected TeraBox/Telegram remains UNVERIFIED.
10. Entire paid photobooks may require licensed purchase; do not bypass authentication, DRM or paid access.

## Implemented
- archive_engine.py: Playwright scripted scroll, dynamic image candidate collection, same-album pagination, permitted CDN/path filters, verified file downloader, manifest and ZIP.
- archive_selftest.py: synthetic test of next page + newly inserted lazy image + srcset largest variant.
- source_targets.json: six known public preview pages, source-scoped filters.
- yui-dynamic-archive.yml: GitHub Actions syntax + synthetic + live crawling tests; private 90-day artifact.

## Unfinished (do not represent as completed)
- Complete coverage of all individual photobooks rather than six catalogue pages.
- Full source-rights / photographer-origin verification, original licensed acquisitions.
- Identity confirmation of all downloaded previews and a permanent independent large storage account.
- Long-lived backing storage and gallery browser of the actual bytes rather than outgoing links.