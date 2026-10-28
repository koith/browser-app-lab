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
7. Validate every individual file with Pillow, byte count, SHA-256 and mobile browser image.naturalWidth. Never create or consume compressed photo bundles.
8. Never claim an empty file hierarchy or a list of remote links is an image archive. Re-check physical stored bytes.
9. External storage needs a real connected account and test upload/download. Unconnected TeraBox/Telegram remains UNVERIFIED.
10. Entire paid photobooks may require licensed purchase; do not bypass authentication, DRM or paid access.

## Implemented
- archive_engine.py: Playwright scripted scroll, dynamic image candidate collection, same-album pagination, permitted CDN/path filters, verified individual-file downloader and manifests.
- archive_selftest.py: synthetic test of next page + newly inserted lazy image + srcset largest variant.
- source_targets.json: six known public preview pages, source-scoped filters.
- yui-dynamic-archive.yml: GitHub Actions syntax + synthetic + live crawling tests.
- public_photo_archive.py + sns_archive.py: explicitly public creator attachments, visible pagination, robots checks, access/rate-limit stop, original bytes, resumable content-addressed individual files.
- collect_public_sources.py + publisher-source-targets.json: publisher model index, public samples, credited Japanese event photographs, photographer portfolio, editorial full-image links/pagination and Korean board article bodies. Catalogue SKUs are separate from acquired photographs and complete editions.
- register_public_photos.py: reviewed photograph types and whole-frame variants, preserved inputs and source provenance, SHA-based append for public timelines, explicit incomplete/public-subset flags.

## Unfinished (do not represent as completed)
- Complete coverage of all individual photobooks rather than six catalogue pages.
- Full source-rights / photographer-origin verification, original licensed acquisitions.
- Identity confirmation of all downloaded previews and a permanent independent large storage account.
- Long-lived backing storage and gallery browser of the actual bytes rather than outgoing links.

## beta.13 publisher browsing and unchanged higher-resolution variants

`publishers.js` groups the catalogue without manufacturing photo acquisitions. Nine publishers plus public/unknown categories expose registered versus actually viewable counts. Eight byte-preserved branding assets have provenance in `publishers.json`; SWEETBOX profile branding and MAXIM parent branding are distinguished from standalone wordmarks, and Yo-U remains unverified.

Four public ImgCup article bodies provide 198 separate image inputs. Conservative whole-frame matching verifies 173 new file SHAs for existing Teddy poses; 25 remain unclassified and unpublished. Select 70 larger 1201x1800 files while retaining the 27 previously larger files. This adds no new complete book or pose and certifies no publisher master. Individual input bytes, alternate sources and SHA-bound selections are preserved. One twice-timed-out file was recovered through its normal browser request and rechecked in the actual lightbox.

`browser_http_bridge.py` preserves the actual browser method, headers and body with normal TLS verification; it does not inject authentication or synthesize an alternate identity. RFC9309 robots unavailable 4xx handling never overrides an actual content denial. CI serializes external-image runs across PR/main without reducing full-gallery criteria. Private cloud upload remains stopped after automatic review interrupted earlier Drive uploads; no alternative upload route is used to evade that interruption.
