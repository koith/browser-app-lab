# YUI personal photo archive — individual files (v0.1.0-beta.2)

This is a personal album viewer. Opening the gallery must show images, not an upload prompt.

## Non-negotiable rules

- No compressed photobook bundles created, imported or required by active workflows.
- Keep each retrieved photo unchanged as an individual image file.
- Maintain album manifests including sequence number, originating public page, bytes, dimensions and SHA-256.
- Preserve web-edition versus licensed publisher-original provenance; never call web previews originals.
- No TinyFish, paid scraper, credit card, or billing prerequisites.
- Do not publish third-party commercial photobooks to an openly accessible static CDN.
- An album counts as available only after actual remote bytes are accessible from the gallery.

## Existing ZIP-free collectors and verified stage

```bash
python apps/yui-gallery/download_jliji_collections.py
python apps/yui-gallery/download_verified_public_album.py
python apps/yui-gallery/cloud/ingest_verified_directories.py \
  yui-jliji-full-private/yuis-present33 \
  yui-jliji-full-private/athletic-club104 \
  yui-jliji-full-private/wet-yui80 \
  yui-jliji-full-private/teddy-bear97 \
  yui-verified-private-albums/green91 \
  --out cloud-stage
python apps/yui-gallery/cloud/test_ingest_directories.py
```

The first collector writes four physical image folders (33, 104, 80, 97 = 314 files).
The second writes public-web image folders, including Green 91 (AI-enhanced).
The directory ingester verifies each image SHA-256 and continuity, preserves the exact bytes
under `cloud-stage/originals/<album-id>/`, generates individual 520px previews under
`cloud-stage/previews/<album-id>/`, and writes `cloud-stage/metadata/catalog.json`.
Nothing is compressed by those stages.

`archive_engine.py` additionally discovers public visible images from allowed sites
with Playwright, keeps individual photo files and per-site manifests, and can promote
authorized public previews to the existing Pages gallery. No bundled archive output.

## Cloud upload (account connection still required)

Existing intended large-volume free remote: TeraBox Basic, unofficial rclone-extra adapter.
Free capacity and nonbilling conditions can change; no unlimited SLA is promised.
The GitHub Actions workflow `.github/workflows/yui-terabox-live-free-upload.yml`
performs retrieval, verified staging, individual remote upload, and readback SHA256 checks
for all 405 originals and 405 previews, when a valid `YUI_TERABOX_COOKIE` GitHub Actions
secret is configured. Never paste credentials into a chat, issue or repository.

```bash
bash apps/yui-gallery/cloud/upload_to_terabox.sh cloud-stage
python apps/yui-gallery/cloud/verify_remote.py cloud-stage archive:YuiArchive --mode media
```

An authenticated read-only gateway is implemented at `cloud/gateway/main.py` for the
`cloud.html` photo viewer. It must be deployed and connected to the user's free
account before online access can be considered complete. The gallery's currently
confirmed public Pages index is only 26 physical previews. The 405 files observed
in CI are public web-resolution copies, not publisher masters, and do not yet count
as live gallery images.

Earlier temporary backup files, including older compressed backups, are historical
safety copies. They are **not** the approved ongoing archive format or user viewing
workflow. Never destroy the only verified existing copy before new remote readback passes.

## QA and truthful counters

- Distinguish URLs found, physical files downloaded, cloud byte readback verified,
  browser-visible photos, iPhone physical-device QA, and publisher-original verified.
- De-duplicate by hash; reject missing sequence members and corrupt image bytes.
- Scheduled crawling is bounded and respects access restrictions; no payment
  circumvention or credential bypass.
- Do not mark photos as stored merely because a thumbnail or URL exists.
