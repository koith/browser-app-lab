## One-to-many public account connection groups (2026-11-02)

The business requirement is to avoid the **incorrect assumption that one SNS
account equals one human customer**. The private account tab therefore
distinguishes (a) observed SNS accounts, (b) **explicitly self-declared,
reciprocally linked account groups**, and (c) **unresolved accounts**.

For example, an entity that *publicly and mutually* claims ten accounts can be
displayed as group **A-[stable ID]** with ten child accounts and the total
distinct source-post count from all ten. The ID is pseudonymous; no legal
name or sensitive identity profile is constructed. These public declarations
are not irrefutable evidence that the same natural person is the operator
(e.g. team/brand pages, account delegation). Neither multiple accounts nor
an unknown account are counted as *confirmed distinct humans*.

Technical approach:
- Official Bluesky `app.bsky.actor.getProfiles` returns public description
  and stable DID; Mastodon account lookup supplies public profile fields.
- A profile must explicitly say the target URL is **its other account** and
  the target profile must **also explicitly claim the source**. Simple
  follows, promotional links, similar handles, reposts and posting-time
  similarities do not become identity edges.
- The server stores canonical URL pairs and verification timestamps, not
  bios, images, captions, personal identity or inferred sensitive traits.
  A link is inactive after 14 days without successful renewal.
- Each hourly index job checks up to 55 previously seen public Bluesky/
  Mastodon accounts using a rotating priority queue. Network or visibility
  failures remain unresolved, not auto-verified.
- Groups are connected components of reciprocal, current public claims. The
  group API `GET /api/account-groups` requires the same private session as
  the rest of the gateway. Group rows expand to show all child account URLs,
  platforms, and observed source-post counts. The source posts use hashed
  original IDs for de-duplication across catalog/discovery ingestion.
- The fallback count is always **unknown human count**, not one person per
  ungrouped account. All such counts are described as account-level metrics.

Research supporting these engineering decisions:
- Mastodon official documentation (HTTPS `rel=me`): 
  https://docs.joinmastodon.org/user/profile/
- AT Protocol official DID/handle identity resolution:
  https://github.com/bluesky-social/bsky-docs/blob/main/docs/advanced-guides/resolving-identities.md
- Splink edge accuracy / precision warning: 
  https://github.com/moj-analytical-services/splink/blob/master/docs/topic_guides/evaluation/edge_overview.md
- IEEE privacy-preserving linkage survey:
  https://signalprocessingsociety.org/publications-resources/ieee-transactions-information-forensics-and-security/2021/01/modern-privacy

**Limitations:** This is a conservative connected-account analysis, not
cross-platform deanonymization. The current gateway does not verify OAuth
ownership claims on X/Instagram/Threads and does not infer anonymous private
profiles from behavioral traits. An operator may choose not to publicly
self-declare their other accounts; those accounts must remain unresolved.
This prevents false positive human identity merges and gives a truthful
statistical denominator. CI's 10-account fixture is synthetic, not a real
person's account portfolio.

## Private indexed account corpus (2026-11-02)

**Code complete; production connection is separately verifiable.** The new
`account_index.py` writes a private SQLite account index from the verified
TeraBox catalog and authorized provider pages. `account_index_sources.py`
adds bounded unauthenticated Bluesky original search, hourly checkpointed
refresh and one-year rolling-window backfill with saturation splitting.
A public API's inability to return a window, pagination restrictions and
rate limits are recorded as incomplete/failed; they must not be treated
as proof that no additional accounts exist. Search results are source
evidence, not individual/person identity.

The gateway includes authenticated
`GET /api/accounts/status`, `GET /api/accounts` (offset/limit/search/platform),
and `POST /api/accounts/sync`, plus same-origin JS/SVG file routes. A separate
private section inside Account Analysis displays the server count and
80-row filtered pages; the public Pages per-session snapshot remains available.
The database stores canonical public profile URLs and SHA-256 post references,
not text, images or behavioral same-person assertions. No client-write endpoint
exists.

**Required gateway configuration before declaring real data indexed:**

- Connect the private HTTPS gateway and TeraBox catalog under the existing
  `DEMAND_VIEWER_TOKEN`, `RCLONE_CONFIG_ARCHIVE_COOKIE`, and
  `DEMAND_TERABOX_REMOTE` requirements. Never place these in the public UI.
- Mount a PRIVATE, persistent, writeable disk for the backend service, and set
  `DEMAND_ACCOUNT_INDEX_DB=/var/data/intersection/accounts.sqlite3` to a path
  **inside the attached disk** (replace path if another persistent mount is
  used). Without this setting, the account API fails closed with 503.
- `DEMAND_AUTO_PUBLIC_INDEX=1` (default when the gateway is running with
  a configured DB): maximum six bounded Bluesky search windows per hour,
  checked against original post ID, author DID, visibility, keyword, and
  timestamp. Set it to `0` to disable network discovery.
- On first activation, verify `/api/accounts/status` after authentication:
  `accounts`, `source_rows`, `last_catalog_sync`,
  `last_catalog_skipped`, `public_scan_windows`. A successful fixture test
  does NOT verify production accounts or complete external platform coverage.
- Verify mounted disk durability by restarting the container and comparing
  account counts, then verify sync/delete consistency and mobile HTTPS.
  Do not deploy a SQLite file on a disposable container filesystem.

**Source coverage:** The public no-key backfill currently covers Bluesky.
X, Threads, Instagram and Reddit may contribute through the already existing
authorized SocialCrawl gateway adapter only when credentials and call budget
are explicitly enabled. Public non-Bluesky feed modules in the static viewer
do not yet upload to this private index. The current system does **not**
establish that all platforms or all years have been indexed.

**QA:** `python -m pytest -q test_account_index.py
test_account_index_sources.py test_gateway.py test_social_sources.py`.
The synthetic 20,000-record volume test is not a real-world crawl.


## Automatic public-account audit (2026-11-02)

The Account Analysis view now begins with an **automatic public-account audit**.
It enumerates every unique, allowlisted canonical public profile URL present in
the **loaded** verified-post/index-candidate snapshot, regardless of whether the
operator added any profiles to the optional watch list. It counts verified and
indexed-only records separately, and paginates accounts at 80 per view. The
existing 80-item limit still applies to *optional manual additional feed checks*,
not the automatic account census.

Cross-platform connected-account groups are shown **only** when each public
profile explicitly links the other profile's canonical URL. They are evidence
of public cross-promotion or self-declared connection, **not a confirmed
individual/person identity**. There is no style/activity/facial/handle
similarity-based inferred identity linkage. Unlinked/unchecked profiles are
unknown, not separate people. The reader automatically checks at most 160
Bluesky profiles (using the unauthenticated official getProfiles API) and 32
allowlisted public Mastodon profiles per page pass, without persistence or
paid calls. Unsupported networks and remaining profiles are not verified for
cross-links. Only profile URLs and live public metadata are used in memory.

**Scope:** This does not convert the visitor's current filtered feed into a
complete all-time index of tens of thousands of accounts. The backend needs
a durable, authorized, pagination-aware account index and a rate-limited
refresh worker to reach that coverage. The browser reports only profiles
actually visible to `INTERSECTION_publicAccountSnapshot()`; no full-corpus
coverage is claimed. Synthetic Chromium QA verifies 20,002 profiles and
a reciprocal-link group; it is a scalability fixture, not a live data census.

# Demand Research — TeraBox private post archive

## Purpose
A publicly accessible **landing/viewer shell** at https://koith.github.io/browser-app-lab/apps/demand-research/ and a separate **private one-click viewer** hosted by the gateway. The private gateway serves both the HTML and API on the same HTTPS origin. The corpus lives in **private** TeraBox. Public GitHub Pages contains NO scraped personal source texts, photos, or videos. A separate authenticated HTTPS gateway reads private TeraBox objects and joins every post's text and attachments in one card. Mobile devices never receive a bulk copy of the archive; they stream only the media needed for display.

## Cloud layout
\`\`\`
archive:DemandResearch/
  posts/<16..64 hex post-id>/post.json
  posts/<16..64 hex post-id>/media/0001.jpg
  posts/<16..64 hex post-id>/media/0002.mp4
  metadata/catalog.json
\`\`\`
Each per-post JSON contains post text, platform, source timestamp, source URL, and a media array. Each media entry has a private key, MIME type, byte length, SHA256 digest, and a boolean \`remote_verified\`. The global catalog is an index, **not** a replacement for the per-post records. Only \`remote_verified:true\` media may appear in the catalog. All files are uploaded to private TeraBox then read back, size/hash verified, and *then* the catalog is published last.

## Connection
The existing gallery already includes a digest-pinned TeraBox rclone-extra uploader. This project is separate: never put research data under YuiArchive or MimmiArchive. This project uses \`archive:DemandResearch\` and supports a separate secret \`DEMAND_TERABOX_NDUS\` (or existing owner-authorized YUI secret in CI, with separate folder).

Backend environment: \`RCLONE_CONFIG_ARCHIVE_TYPE=terabox\`, \`RCLONE_CONFIG_ARCHIVE_COOKIE=<SECRET>\`, \`DEMAND_TERABOX_REMOTE=archive:DemandResearch\`, \`DEMAND_VIEWER_TOKEN=<random >=24 chars>\`. The HTML page never receives the cloud cookie. Use HTTPS for gateway, and configure its URL in the frontend during deployment. CORS is restricted to koith.github.io; no public API access without bearer token. A short-lived signed media URL is used to support native iOS video with HTTP Range requests. Signing URLs are not stored permanently.

## Upload tool
\`\`\`bash
python apps/demand-research/upload_verified.py --stage <private-local-stage> --remote archive:DemandResearch
\`\`\`
The staging folder contains \`posts/<id>/post.json\` and the indicated physical media files. Never commit stage files to a public repository. Ingest only data with valid preservation rights/consent; sexually sensitive identifiable data may require additional consent and deletion handling. Upload failure must **not** report data saved. Do not claim an original file exists merely from its URL or blob metadata.

**Status:** HTML and backend code are ready, but *actual cloud upload, private gateway deployment and phone QA remain unverified* until connected account secrets, a permitted post-bundle stage and cloud read-back exist. No synthetic items are ever represented as actual collected records.

## Tests
\`\`\`bash
pip install fastapi uvicorn httpx pytest
cd apps/demand-research
python -m pytest -q test_gateway.py
\`\`\`

## Multi-source public discovery (2026-11-02)

The public viewer now attempts Bluesky API plus Mastodon public hashtag feeds
(with bounded public-timeline fallback), Misskey search on misskey.io and hoto.moe,
Lemmy search (v3 with v4 fallback), and PullPush's publicly indexed Reddit
submissions. It keeps origin links and platform badges, applies exact keyword,
visibility and date filters, and deduplicates by origin ID. A successful HTTP
request **does not** imply that the query matched any posts; CORS, authentication,
server coverage, federated indexing, and archive latency may yield zero.

X/Twitter, Instagram and Threads are **not** represented as connected sources:
reliable official full-text access requires separate approved API credentials,
and no paid requests have been enabled. Neither synthetic browser fixtures nor
an API adapter alone establish real-world ingestion. Live provider counts and
mobile deployment remain independent acceptance checks.

## Opt-in authenticated cross-network search (2026-11-02)

The private FastAPI gateway now includes a **server-side SocialCrawl adapter**
for public X, Threads, Instagram Reels and Reddit keyword searches. The
browser never receives its upstream API key. Results use a shared post schema,
strict origin/profile URL checks, keyword/date filtering, de-duplication and
one-page requests. An explicit SNS search button in the **private viewer**
requests one provider and one term; there is no automatic paid search on page
load. All results are memory-only with a 10-minute cache, and **not uploaded**
to GitHub Pages or TeraBox. Users must follow provider/platform terms and
deletion requirements.

Required runtime values (private gateway only):

- `DEMAND_SOCIALCRAWL_API_KEY`: operator-controlled key from https://www.socialcrawl.dev/.
- `DEMAND_SOCIAL_SEARCH_ENABLED=1`: explicitly opt in after reviewing cost.
- `DEMAND_SOCIAL_MAX_DAILY_CALLS=1`: one **best-effort per-process** daily request limit; increase deliberately with billing monitoring. This is not a global or hard financial cap, particularly when multiple workers or redeploys are involved. Configure a hard provider-side spending cap or durable shared rate limiter before broad production use.
- Existing `DEMAND_VIEWER_TOKEN`, TeraBox secret and HTTPS private gateway must be configured; `/api/discovery` requires the signed private-viewer session cookie.

Status and source search: `GET /api/discovery/status` and
`GET /api/discovery?platform=x&term=...&start=2026-10-01&end=2026-11-01`.
The latter is disabled unless all opt-in configuration is present.
All search results are restricted to the requested 30-day window
(up to 32 calendar days).

`/api/discovery` is **not** served by GitHub Pages; this is intentional
because a public keyless proxy could create unbounded API charges. The
public viewer remains limited to public no-token adapters, whose
actual X/Threads/Instagram coverage is zero. Full live collection,
private gateway deployment, vendor-account connection and iPhone testing
are **NOT YET VERIFIED**.

Validation: `cd apps/demand-research && python -m pytest -q test_gateway.py test_social_sources.py`.
Fixtures represent synthetic rows only; passing these tests does not imply
live records exist.

## Current operation — automatic unified multi-SNS feed (2026-11-02)

**No "다른 SNS 게시글 찾기" section, button, platform selector, or extra user action.**
The public GitHub Pages viewer runs one bounded background discovery pass when
the page opens, in parallel with its Bluesky/Mastodon/Misskey/Lemmy/Reddit adapters.
The free anonymous Keenable + Firecrawl endpoints are called once each per
X/Threads/Instagram (six network-search calls total, on the visitor's network).
Each canonical post-link candidate gets a platform logo, the correct original
permalink and an author-profile URL when the URL supplies the handle. Duplicate
search-result URLs are collapsed by platform post ID. These results are
**interleaved within the one main feed**, not kept in a special section hidden
below hundreds of Bluesky cards.

**Source accuracy and dated filtering:**
- Search-index entries are conspicuously tagged `링크 · 원문 미확인` or
  `검색어·원문 미확인`. They show `작성일 미확인 · 검색 결과`, no
  synthetic date, and an original-source link. Such entries are **not** counted
  as confirmed collected posts, even though they appear in the one feed.
  Their date-range membership is unknown; the detail dialog states this.
- For a bounded set of public X candidates, the third-party no-key FxEmbed
  reader is queried and exact ID, source timestamp, visibility and required
  text match are checked. Only matching originals inside the selected date
  range become **real dated X post cards**; the link candidate disappears
  when an original is admitted.
- Threads/Instagram may yield cached public-page text via a separate bounded
  Keenable fetch, but this is **not authoritative publication timestamp proof**,
  so those remain explicitly indexed-link candidates.
- Existing date selector, one `더 보기` control, source badges, advertising
  filter and original-link/author-link navigation are preserved. Changing the
  period reapplies the date window to already verified originals without
  repeating all six index searches.
- No keys, credentials, login, paid services, media downloads, account
  targeting, cloud storage, or persistence of possibly sensitive indexed
  content. Provider limits and removals are respected; all-public SNS
  completeness cannot be guaranteed by a search index.

**Verification:** `python apps/demand-research/test_free_discovery_browser.py`
covers automatic calls, interleaved cards, source URL/domain checks,
dated-source promotion, and period-change replay using synthetic responses.
`--live` calls actual free providers in Chromium and reports aggregate
results without saving usernames, post text or URLs. The existing
`test_live_browser.py` checks the Bluesky and combined viewer separately.

--- Historical implementation notes below (manual UI removed) ---

## Historical verified zero-key public SNS search link discovery (2026-11-02)

Public Pages now offers a user-triggered, independently-labelled indexed-link discovery feature in free_discovery.js. This feature NEVER changes real Bluesky post counts and NEVER pretends index candidates are verified original posts.

- Keenable public no-key endpoint: POST https://api.keenable.ai/v1/search/public, X-Keenable-Title header, keyword and site restriction, max 10 results.
- Firecrawl public no-key endpoint: POST https://api.firecrawl.dev/v2/search, web-only, max 10 results. No key or billing data is supplied. The provider enforces shared-IP daily requests/credits; an HTTP 429 ends use, with no automatic paid upgrade.
- A click triggers at most two requests and no request happens automatically. Browser-side per-session 12 click courtesy guard and 10-second cooldown; these are not global abuse controls.
- Validate canonical X status, Threads post and Instagram p/reel links with strict domain/path allowlists, reject spoofed domains and HTTP links, deduplicate by platform post ID, and display snippets as plain text (no injected HTML). Author profile links are shown only when a permalink contains a defensible handle. Candidate links open in a new tab.
- These search-index candidates lack verified original content, original timestamp and certainty of visibility. They are displayed separately, without fabricated dates and outside the cloud catalog or real posts feed. Never copy indexed sensitive personal data to a public archive.

**Live GitHub Actions evidence:** On 2026-11-02, Firecrawl returned 2 canonical X, 8 Threads and 4 Instagram links; Keenable returned 7 X, 8 Threads, 0 Instagram links for initial project terms. These are NON-DEDUPLICATED search result URL candidates, not true confirmed live posts; repeat queries showed result variation. Five X candidate original-status checks were inconclusive. Both providers returned CORS preflight success for https://koith.github.io. Prior Bing RSS tests returned 0 canonical social-post links. An additional direct no-key source benchmark validated public X single-post lookup through FixTweet/vxTwitter, Telegram 20 message previews, a scoped Arctic Shift Reddit feed with 3 posts, and Misskey/Nostr control-word searches; none proves project-term full-text coverage.

Browser QA: python apps/demand-research/test_free_discovery_browser.py, and --live for real provider CORS/data in Chromium. CLI source probes: probe_free_sources_v2.py, probe_free_index_v2.py, probe_keyless_search.py, probe_live_verify.py. All CI probes print aggregate counts only and do not retain personal text, URLs, usernames, media or IDs.

Source documentation:
- Firecrawl free keyless IP daily limits: https://github.com/firecrawl/firecrawl-docs/blob/main/rate-limits.mdx
- Firecrawl search operators and limits: https://github.com/firecrawl/firecrawl-docs/blob/main/features/search.mdx
- Keenable free search pricing: https://keenable.ai/pricing
- socialfetch public single-post and Telegram viewer: https://github.com/EdgeAIG/socialfetch

Provider terms, indexing, deletion and CORS rules can change. Keyless index search is a link discovery aid, NOT completeness evidence, a right to republish, or a guarantee of zero errors.

### Follow-up original verification (2026-11-02)

- A second FxEmbed X status comparison corrected a date-parser false negative. Five public X original records resolved with HTTP 200, and two contained the requested literal project keyword. **None** was posted in the preceding 32 days. One keyless Firecrawl original-page scrape also returned HTTP 200, non-empty page text containing the term, but no published-date metadata. Repeated original scrapes remain unreliable: first X request timed out, and Threads/Instagram returned 403.
- FxEmbed v2 global search is **NOT** a current viable keyless discovery source: despite documented GET /2/search, both project and neutral control queries returned HTTP 404 (see open public upstream issue). Single X original lookup is a separate successfully verified feature, not proof that global X search works.
- In Chromium running at the GitHub Pages origin, GET https://api.fxtwitter.com/status/20 returned HTTP 200 with a public post and readable JSON via CORS. A manually clicked **X 공개 원문 확인 (무료)** action uses this free endpoint to check the exact post ID, content, keyword and actual provider timestamp before optionally displaying the text. This is an unofficial third-party API, not X's first-party proof; other provider data are still marked indexed-only. No automatic mass collection, storage or download occurs.

## November 2: real multi-network discovery + header simplification

- The `All`/`뒷계`/`섹트`/`일탈계` **topic tabs were removed**. The public post feed always includes all three established keywords; its date picker now shares the INTERSECTION title row at desktop and iPhone widths.
- The zero-key discovery panel now appears **before the first feed card** rather than after hundreds of Bluesky cards. Its default selections are `전체 SNS` and `전체 검색어` (X, Threads, Instagram × all three keywords), with an explicit `다른 SNS 전체 조회` button. Optional source/term selectors are not tabs.
- A click sends a bounded six requests (3 networks × KeenAble/Firecrawl) with per-provider caps 35/20, no credentials, and no payment. Rate limits or 403/429 do not trigger proxy rotation, bypass, or paid fallback. Results are validated by strict HTTPS host/permalink allowlist, merged across providers and presented as **indexed candidates** with visible source badges and original/profile links.
- The free public X original reader (FxEmbed unofficial API) can check post ID, body and real source creation time. **Only** a matching, public original posted inside the user-selected period may enter the main feed (memory-only) via `INTERSECTION_acceptPublicX`. Original verification never downloads image/media or saves a post in the repo/cloud. Eight-/nine-candidate batch verification is bounded and only occurs after the user explicitly triggers all-network search.
- Threads/Instagram `Keenable /v1/fetch/public` may return actual indexed public-page text for a matching canonical URL. It is labelled a **third-party page extraction** (may be cached), not an original publication-time proof and not automatically admitted into the real dated feed. At most 4 Threads + 3 Instagram candidate pages are checked after an explicit all-SNS click. Users can open the original page. Date-unknown candidates are never counted as verified dated records.
- The public GitHub Actions live source feasibility probes reported for one multi-keyword query: KeenAble **29 canonical X**, **12 Threads**, **9 Instagram** index links, not deduplicated across runs and not verified as current matching posts; Firecrawl could return HTTP 403 after quota/network restrictions. Previous Meta tokenless oEmbed on example Instagram public URLs returned HTTP 200; sampled Threads oEmbed returned HTTP 400. A Keenable public fetch request returned HTTP 200 for selected Threads/Instagram public pages, but original date and true post identity remained unproven.
- Static browser QA exercises unchanged Bluesky feed, tab absence, title/date vertical alignment at 390px, date dialog, source badges, one-click all-network search, date-checked X admission and provider errors. In data-sensitive contexts no indexed post text/URLs are logged to public Actions outputs; only aggregate diagnostics.

**Acceptance boundary:** The user's largest limitation is still the high-fidelity *recent full-text original collection* across Threads and Instagram, which cannot be asserted from indexed links alone. Official Threads keyword search is a separate no-fee option that requires Meta app review for `threads_keyword_search` permission, and may suppress sensitive topics; this is not enabled without the approved token. All read requests follow provider visibility, rate limits and deletion policies.


## Additional free source & community research (2026-11-02)

Read [SOURCE_COMMUNITY_FIELDGUIDE_20261102.md](./SOURCE_COMMUNITY_FIELDGUIDE_20261102.md) for a verified, citation-linked comparison of open-source scrapers, actual maintainer issue comments and pull requests, 2026 Reddit/DEV development discussions, official quota restrictions, and independent anonymous live probes. It differentiates VERIFIED results from proposed source integrations and gives priorities for genuine dated post acquisition, not just index links.


## 2026-11-02: public account watch, source-level dedup and commerce signals

A second top-level **계정 분석** tab has been added; the existing unified post feed remains the default. The account page saves **opt-in public profile URLs** in the user's browser only (up to 80). Users can add from a post-detail button, enter a public profile URL, inspect the account, refresh eligible source feeds, search watched profiles and remove an account.

- Local browser storage contains only the manually selected normalized public profile URLs; no posts, media, word-based behavior history, cookies, credentials or cross-platform identity mappings are persisted. Refresh results remain in tab memory.
- Verified public posts are included only for the selected period. Indexed links lacking original dates are counted and labelled separately; they are not promoted to verified data.
- Direct public feed support: anonymous Bluesky app.bsky.feed.getAuthorFeed, anonymous Mastodon account lookup and public-status fetch, and bounded X keyless search with public FxEmbed single-status original checks (ID, exact author handle, visibility, timestamp). X reader is unofficial and fallible. Replies/reposts and nonpublic statuses are never used to claim public authoring. Other networks still use matching posts already in the global feed.
- Up to four previously opted-in supported accounts are refreshed at page load; other checks are on user click. In-memory source cache lasts 10 minutes, source calls have a 13-second timeout, and no background polling is scheduled.
- Account analytics: source-specific account ID, number of verified sample posts, date of latest observed post, current seven-day chart, and exact-commerce-word occurrence counts. Across followed accounts, duplicate normalized commerce texts are counted only once, separately showing repeat counts.
- **One distinct account is not one distinct real person.** Cross-platform pseudonymous identity resolution is not inferred or implemented; this protects against false unique-people claims and unintended deanonymization. The dashboard reports accounts and deduplicated public content, never unique individuals, actual purchases, or sensitive personal traits.
- Public profile URLs use an HTTPS hostname/path allowlist. Any untrusted public source text is displayed using textContent, not inserted as HTML. No account list or source posts are sent to a new service.

Test: python apps/demand-research/test_account_watch_browser.py (mobile Chromium fixture). The GitHub Pages and post-merge CI runs must pass before declaring this deployed; physical iPhone QA is pending.
