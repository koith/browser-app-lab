# Public gallery photo engines — actual A/B, 2026-11-01

Verified live GitHub Actions run: https://github.com/koith/browser-app-lab/actions/runs/41292593281
Branch: research/gallery-full-engines-ab-benchmark-20261101
Compared existing `direct_photo_pipeline.page_images` with real installed `gallery-dl 1.32.19`, `Scrapy 2.19.0` HTML selectors, and Playwright Chromium browser rendering on the SAME public photo pages (plus separately labelled same-creator Twitter vs teapawt experiments).

This is a **sample of nine public first-page/source paths**, not a full-work completeness study. Each counted URL passed actual HTTP download, image decoding, and SHA256. It is not stored to TeraBox unless a *separate* storage workflow read back and verified the file. Research candidates must not appear in the photo gallery.

| Model | Public work page | Baseline unique decoded photo asset groups | Ensemble author/work-scoped groups | Additional unmatched groups | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| Yui | DJAWA Privaty | 27 | 27 | 0 | 52 further SHA files are WordPress resized renditions of existing photo paths, not 52 extra cuts |
| Yui | ArtGravia Vol.677 nicesss | 4 | 4 | 0 | Four ordinary public source previews |
| Yui | ArtGravia Vol.693 ShowArtx | 0 | 0 | 0 | 403 for requests and Chromium, gallery-dl has no matching extractor |
| Yui | Verified `super_yuisan` timeline via teapawt + gallery-dl direct X | 17 | 17 | 0 | Generic HTML gathered 59 additional SHA with ambiguous direct authorship / avatars / multiple renditions; **quarantined**, not photo acquisitions. Author-scoped browser reparse finds only 17. Native gallery-dl emitted 0 |
| Mimmi | DJAWA In the summer sunshine Part 2 | 16 | 16 | 0 | 61 extra SHA are resized renditions of known original paths; not extra photo cuts |
| Mimmi | ShyPetal My Summer Vacation Vol.5 | 45 | 45 | 0 | 45 public image files decoded after admitting specifically declared image host; the owner archive already indexed 60 positions for this work at the audit date |
| Mimmi | PixiBB My Small Bird (first page only) | 10 | 10 | 0 | Page links to **13 more source pages**; this pilot is not the full album |
| Mimmi | V2PH album page | 0 | 0 | 0 | Ordinary public request and browser 403; do not bypass |
| Mimmi | `Mimmi_official` timeline direct X | 0 | 0 | 0 | teapawt path returned 404, native gallery-dl emitted 0 |

**Conclusion:** There is NO evidence that the in-house collector is generally superior to open-source alternatives. On these *specific page types*, the baseline recognizes native images better than naive generic HTML. The extracted 113 WordPress resized variants had different SHA-256 yet add **zero different photo groups**, so raw SHA counts alone are an invalid metric. A generic social-feed scan also pulled unverified other-author/media candidates; direct-author checks are required.

**Remaining mandatory comparison:** follow all observed pagination pages, search more actual model works and alternative photo hosts (including supported gallery-dl ecosystems), use pHash/decoded pixels on cross-origin versions, and then require physical individual owner storage, exact remote SHA readback and live gallery open QA. A first-page 10-photo count must not be labelled a complete 135-photo work. Reuse the workflow and extend its source registry; do not substitute software-engine novelty for genuinely additional verified photo cuts.

Collection safety: no creds, no paywall bypass, no generated URL enumeration, no changes to private owner gallery in this A/B workflow.
