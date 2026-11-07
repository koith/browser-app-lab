# Render-independent private photo transport — NOT DEPLOYED

The suspended Render service cannot serve its private originals. This staging
transport reads the owner's existing private R2 binding **or** a private B2/R2
S3 bucket. It creates no account, subscription, bucket, media copy or Worker.
Neither gallery switches to this endpoint until real storage and production
browser acceptance have passed. Local tests are not cloud migration evidence.

## Storage and signing

Use `ARCHIVE_BUCKET` for an R2 Standard binding. Alternatively configure these
Worker-only values for a private S3 bucket:

| Worker setting | Existing backfill configuration |
| --- | --- |
| `OWNER_S3_ENDPOINT` | `RCLONE_CONFIG_OWNERREPLICA_ENDPOINT` |
| `OWNER_S3_BUCKET` | `OWNER_REPLICA_BUCKET` |
| `OWNER_S3_REGION` | `RCLONE_CONFIG_OWNERREPLICA_REGION` |
| `OWNER_S3_ACCESS_KEY_ID` | A separately limited read-only application key |
| `OWNER_S3_SECRET_ACCESS_KEY` | Its Worker-only secret |

The S3 reader accepts only HTTPS B2 regional endpoints or the account's R2
endpoint (`auto` region). It signs GET requests with AWS SigV4, forbids redirects,
limits streamed and declared sizes, and treats only 404 as absence. Provider
errors and signed upstream requests never enter browser responses or logs.
Catalogs cache for 30 seconds across S3 adapter instances. Originals are never
recompressed, resized or replaced by unrelated photos.

`PAGE_ORIGIN` is `https://koith.github.io`. `SIGNING_KEY` is a separate random
Worker-only secret of at least 32 characters. The default policy also requires
`VIEWER_TOKEN_SHA256`, the digest of a private viewer bearer. Never embed that
bearer, signing key or bucket credentials into Pages sources.

An explicit `PAGES_READ_POLICY=existing-sha-pinned-gallery` instead supports the
existing passwordless Pages photo-read contract. Only that policy permits a
signing request without a bearer, from the configured page origin and with the
exact known photo SHA. This is **not** user authentication: SHA values are public
metadata and CORS is a browser restriction. It intentionally grants existing
gallery visitors photo access, without making the bucket public. Leave the
default policy in place for archives that must require a viewer identity.

`POST /api/v1/sign` accepts `{model,album,number,variant,sha256}`. It looks up
`<model>/metadata/catalog.json` privately and returns a five-minute URL bound to
the photo's SHA and byte length. `GET /api/v1/media/...` verifies the signature
before a storage read, then validates the canonical key, exact bytes, SHA and
image magic. Original tabs may use the signed URL without an Origin header.
Bad authorization, hashes and namespaces fail closed.

`pages-client.mjs` requests those URLs without storage credentials, validates
their origin/path/SHA/length/expiry, and deduplicates signing requests. A missing
preview can use only the same photo's verified original. Authentication failures
never fall through to Render or a third-party image site. This module is not yet
activated in either gallery; an unprovisioned endpoint cannot restore photos.

## Required production acceptance

1. Verify the owner's account, current free allowance and inability to incur
   unauthorized charges. Published free quotas do not verify an account's billing
   settings. Do not create billed resources or enable a paid plan.
2. Use `apps/gallery-archive/backfill_private_owner_replica.py` with a separate
   limited write key. Verify private bucket settings before writes; retain the
   original TeraBox data and the existing immutable object layout. Every uploaded
   file requires an independent remote SHA/byte/dimension readback.
3. Verify both private catalogs and every target original. Preview presence needs
   separate evidence. Worker limits are 6 MB/catalog and 8 MB/photo; inspect actual
   inventory and free-tier limits before deployment.
4. Deploy the Worker with read-only credentials, verify real cloud reads, then
   activate the client in both existing galleries without adding login/import UI.
5. Verify the exact deployed SHA in mobile WebKit and Chromium: covers, album
   photos, originals, navigation, reload, native original tabs, and no Render
   dependency. Count successful actual photos, not metadata entries.

None of those cloud milestones is completed by this directory's tests.

## Local and CI verification

Install `botocore==1.40.70` in a development virtual environment, then run:

```sh
node apps/gallery-archive/cloudflare-owner-gateway/worker.test.mjs
node apps/gallery-archive/cloudflare-owner-gateway/private-s3.test.mjs
```

The first suite checks default authorization, opt-in Pages access, signed-URL
validation and exact readback using an already-public gallery JPEG. The second
compares SigV4 against the independent botocore S3 signer with dummy credentials
and tests a loopback HTTP object server. It does not contact or validate a real
cloud bucket, upload a new photo, verify model identity or test a deployed gallery.
Set `PYTHON_FOR_SIGV4` when botocore is in a non-default Python environment.
