# 2026-10-29 — Two galleries: physical-byte-only handoff

## User's nonnegotiable definition
- Gallery = actually downloaded/stored image files that render even when original source domain becomes unavailable; never a relay/hotlink gallery.
- An external URL, source page, SHA recorded by a crawler, or a preview that renders from an external CDN does NOT count as saved.
- Show only displayed, physically saved originals or verified copies. Preserve original bytes/album numbering. Do not claim completeness for a partial set.
- Do not put private archive files in public GitHub Pages or make private Drive files public.

## Physical archive snapshot at PR #272
- Yui: `apps/yui-gallery/stored-albums.json` references **23 physically committed public-preview images** in **6** collections. External-source indexes `source-viewer-albums.json` and `additional-source-albums.json` are **research/acquisition metadata only**. Prior displayed source-link counts in `version.json` are historic, not live saved counts. Yui private authenticated gallery gateway is not configured; primary TeraBox `not_connected`.
- Mimmi: `apps/mimmi-gallery/stored-albums.json` at baseline main commit `328b671aa6dd77ee6df719ec44f898ee871c960c` records **2,162 saved original-byte JPEG files**, **57 albums**. Its `mimmi-stored-public-gallery.yml` automation runs 8 times/day and may increase totals; always re-read live main. Its test verifies SHA-256 of each image byte.
- Yui **additional real private Drive backup**: Google Drive private folder `Yui_public_individual_2026-10-28`, folder ID `18Y0PToB2_Ns8c4WSafg6LVyZMK_OEVFV`, **218 individual JPEG files, 68,957,163 bytes**. All 218 were downloaded through the user's connected Drive, verified with file name SHA-256 and decoded using Pillow. **217 files match hashes from `additional-source-albums.json` album `public-yui-sns` (nominal 361 source entries), 1 matches `acosta-japan-public-report`.** Not complete editions. Only 1 copy per SHA; some hashes appear as references in more than one source collection. Never inflate counts by duplicated refs.
- Those 218 files were packaged into a separate private, self-contained downloadable ZIP with actual bytes, manifests and an offline `index.html`, surfaced directly to user in ChatGPT. The ZIP was not published to GitHub. Do not claim that online Pages displays these 218 files yet.

## PR #272 changes
- Yui visible app now reads actual `stored-albums.json` or `YuiPrivate.albums()` only, validates local relative image path and SHA/bytes, and shows the resulting archived count. Research-only source URLs are not fetched for display, and album click no longer opens an external source site.
- Mimmi keeps stored-only app and no longer opens a source URL as a fallback to a gallery card.
- Yui version beta.20. Replace legacy source-request smoke tests with full stored media checksum and mobile Chromium/WebKit decode tests and local 451/503 fixtures.
- Correct old album alias behavior: if alias points to an unarchived collection but original ID still has physically saved images, preserve the original ID.

## Next tasks, not completed
1. Connect and authenticate a private durable Yui media origin; it must serve real saved original bytes and protect access. Current `YuiPrivate` client validates each byte against SHA and expected size. Private Drive OAuth or another owner-authenticated free service is a candidate, but requires real user-controlled credentials/consent.
2. Import/mount 218 verified private Drive originals into that origin, matching by SHA to existing source collection; confirm all 218 are displayed by actual iPhone gallery in authenticated mode. Do NOT paste these private originals into public GitHub Pages.
3. Continue acquiring missing images through normally accessible sources; verify bytes, dimensions, SHA, file persistence and actual viewer output, never advertise source-only rows as complete physical collections.
4. Continue Mimmi physical-storage batches using the existing scheduled workflow; don't interfere with the publisher bot or duplicate Git history.
5. Check Actions of PR #272 and Pages deployment; avoid claiming physical iPhone hardware QA when only simulated WebKit has run.

## QA evidence boundary
- Source URLs remain in discovery manifests, for crawler reference only.
- Physical stored files can be counted only after repository/owner storage SHA verification.
- Successful GitHub CI browser tests mean a simulated mobile engine, not a user-handset validation.
