# Render-independent private R2 viewer transport (STAGING ONLY)

This is a **not yet deployed** read-only Cloudflare Worker for existing owner photos.
It **does not** create a Cloudflare account, a paid subscription, a bucket,
a public domain or any media copy. The Render gateway remains unchanged.

* Private R2 Standard binding: `ARCHIVE_BUCKET` (no `r2.dev` public URL).
* `VIEWER_TOKEN_SHA256`: SHA-256 digest of a randomly generated, private
  viewer bearer secret; NEVER put the secret in GitHub Pages sources or logs.
* `SIGNING_KEY`: separately generated random Worker-only secret of at least 32 chars.
* `PAGE_ORIGIN`: `https://koith.github.io`.
* `POST /api/v1/sign`: bearer-authenticated request for one known
  `{model,album,number,variant}` after reading the model's private canonical
  `<model>/metadata/catalog.json`. Returns a five-minute SHA/size-bound URL.
* `GET /api/v1/media/<model>/<album>/<number>/<variant>`: validates signature
  BEFORE touching private storage, rereads canonical catalog, retrieves only
  its recorded immutable R2 key and validates exact byte length and SHA-256.
  Rejects missing, damaged, unknown or unmirrored photos.
* Strict image-magic MIME, no-store API responses, no credentials in image URLs.

Backfill uses existing `apps/gallery-archive/backfill_private_owner_replica.py`:
original TeraBox owner data stays untouched; every uploaded R2 object requires
independent SHA readback. Do not enable the Worker until the complete catalog
and target image objects were verified in the owner's **private** R2 Standard
bucket. The current inventory's largest actual indexed original is < 2.5 MB;
the Worker conservatively rejects objects larger than 8 MB. Verify previews
before claiming 100% coverage.

For security, the Worker is intentionally NOT wired into the public Pages
gallery here. The next integration must pass the viewer bearer only through
a direct authorized API call and then render the returned short-lived image
URL. Do NOT bake a global bearer or R2 credentials into JavaScript shipped to
GitHub Pages. No silent public-photo publishing is permitted.

Run `node --test apps/gallery-archive/cloudflare-owner-gateway/worker.test.mjs`.
Actual private-R2 writes, Worker deployment, Pages browser integration and
iPhone cold-start acceptance remain separate OPEN milestones.
