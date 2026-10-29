# 2026-10-29 — Personal ZIP vault implementation handoff

## Requirement and completed code
Both `apps/yui-gallery/` and `apps/mimmi-gallery/` must render actual stored bytes, never hotlinked research URLs. Work from PR #272 is still in place.

This branch adds the same locally bundled `photo-vault.js` to each gallery, with canonical source `apps/photo-vault.js`. `index.html` has an unobtrusive **내 ZIP 보관본 가져오기** action and an IndexedDB-backed `vault:` photo path. File thumbnails, album covers, full-screen viewer and counts reflect imported verified bytes. The galleries are independent by model, but the IndexedDB database exists under the same browser origin.

The owner media API remains optional and unchanged. Local public archive photos remain visible even if no ZIP was imported.

## ZIP import integrity
- Accept explicit `manifest.json` and `photos/<sha256>.<jpg/jpeg/webp/png>` entries, including one enclosing root directory.
- Confirm `model` matches `yui` or `mimmi`, photo count, byte lengths, SHA-256, image dimensions metadata, and safe IDs/paths before treating a photo as archived.
- `Blob` slices from selected ZIP may fail `IndexedDB` on WebKit. Convert the data into an `ArrayBuffer`, then persist that; create a Blob on readback and re-check SHA-256. This fix is required to pass the iPhone-like QA.
- Browser storage is local to that browser/device and can be deleted by clearing site data. **It is not a remote cloud connection, cross-device synchronization, private encrypted vault, or permanently hosted cloud service.** Retain the original ZIP as backup.
- Source host image URLs are never fetched during browsing.

## Private recovered image backup
A private Drive folder `Yui_public_individual_2026-10-28`, ID `18Y0PToB2_Ns8c4WSafg6LVyZMK_OEVFV`, contains 218 unique original JPEG files (68,957,163 bytes), verified individually. 217 hashes map to `additional-source-albums.json` collection `public-yui-sns`, and one hash maps to `acosta-japan-public-report`; these are incomplete collections, not a finished 218-page publisher photobook.

The assistant produced a personal, all-`ZIP_STORED`, import-compatible archive in its current attachment container, named `yui_218_import_ready.zip` (69,150,574 bytes) with `YUI_218_OFFLINE/manifest.json`, `photos/` and an offline `index.html`. This ZIP is provided as a user download, not uploaded to the public repository. Once the deployed gallery accepts ZIP, the user can choose it directly on the iPhone.

## QA
`.github/workflows/shared-private-vault.yml` builds real image ZIP fixtures using `apps/test_photo_vault_fixture.py`, then tests with `apps/test_photo_vault.cjs` under Chromium and WebKit:
- Imported Yui 1 genuine file and retained the existing 23
- Imported Mimmi 1 genuine file and retained the existing 2,162
- Viewer renders a `blob:` URL from persistent local bytes
- Reload does not clear saved images; different models don't leak albums
- Corrupt ZIP gets rejected with no fake album count
- Zero requests to external image servers

Existing gallery QA still checks actual committed SHA-256 bytes and remote media access restrictions. A successful simulated WebKit run is not a physical iPhone test.

## Remaining
- Acquire missing individual publicly accessible photos from source catalogues; verify bytes, hashes and complete album membership without bypassing paywalls or access restrictions.
- For automatically shared private access across devices, set up a user-authorized personal media service (Google Drive OAuth requires a real registered client ID and user consent; do not invent one), or another real private gateway. IndexedDB ZIP import is an immediate device-local interim method.
- Both gallery counts must include **only** actually saved and rendered images. Do not claim any missing sets are stored just because research manifests contain their URLs.
