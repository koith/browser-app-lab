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

## Verified zero-key public SNS search link discovery (2026-11-02)

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