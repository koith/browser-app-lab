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
# Fail closed: copy/size equality does not prove remote image integrity.
# Read every original and thumbnail back from the private account and SHA256 it.
python3 "$(dirname "$0")/verify_remote.py" "$STAGE" "$REMOTE" --mode media --workers 3

# The provider is not claimed by the staging catalogue until after real readback.
python3 - "$STAGE/metadata/catalog.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
catalog=json.loads(p.read_text(encoding="utf-8"))
catalog["storage_provider"]="terabox"
p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
PY

# Persist the complete remote hash report before publishing a discoverable catalogue.
rclone copyto "$STAGE/metadata/remote-verification.json" "$REMOTE/metadata/remote-verification.json"
rclone copyto "$STAGE/metadata/catalog.json" "$REMOTE/metadata/catalog.json"
python3 "$(dirname "$0")/verify_remote.py" "$STAGE" "$REMOTE" --mode catalog
echo "TeraBox uploaded: all originals/previews and catalogue passed remote SHA256"
