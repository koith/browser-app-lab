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
