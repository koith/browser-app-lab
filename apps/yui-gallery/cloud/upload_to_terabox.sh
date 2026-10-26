#!/usr/bin/env bash
set -euo pipefail
STAGE="${1:-cloud-stage}"
REMOTE="${ARCHIVE_REMOTE:-archive:YuiArchive}"
if [[ ! -d "$STAGE/originals" || ! -f "$STAGE/metadata/catalog.json" ]]; then
  echo "Missing validated original files and catalog in staging directory" >&2; exit 2
fi
if [[ -z "${RCLONE_CONFIG_ARCHIVE_COOKIE:-}" ]]; then
  echo "NOT CONNECTED: RCLONE_CONFIG_ARCHIVE_COOKIE must be set securely" >&2; exit 3
fi
export RCLONE_CONFIG_ARCHIVE_TYPE=terabox
if ! rclone listremotes | grep -qx 'archive:'; then
  echo "TeraBox backend unavailable or session invalid" >&2; exit 4
fi
rclone copy "$STAGE/originals" "$REMOTE/originals" --transfers 3 --checkers 4 --retries 3 -P
rclone copy "$STAGE/previews" "$REMOTE/previews" --transfers 3 --checkers 4 --retries 3 -P
rclone check "$STAGE/originals" "$REMOTE/originals" --size-only --one-way
rclone check "$STAGE/previews" "$REMOTE/previews" --size-only --one-way
rclone copyto "$STAGE/metadata/catalog.json" "$REMOTE/metadata/catalog.json"
echo "Local catalog hash:" && sha256sum "$STAGE/metadata/catalog.json"
echo "Remote catalog hash:" && rclone cat "$REMOTE/metadata/catalog.json" | sha256sum
echo "TeraBox upload and remote verification complete"
