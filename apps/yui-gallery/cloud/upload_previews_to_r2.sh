#!/usr/bin/env bash
# Optional, private preview-only cache. Originals NEVER enter R2.
set -euo pipefail
STAGE="${1:-cloud-stage}"
REMOTE="${R2_PREVIEW_REMOTE:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${R2_CACHE_WRITE_APPROVED:-}" != "1" ]]; then
  echo "R2 uploads require explicit R2_CACHE_WRITE_APPROVED=1 (billing may apply)" >&2; exit 2
fi
if [[ ! "$REMOTE" =~ ^previewcache:[A-Za-z0-9._/-]+$ ]] || [[ "$REMOTE" == *..* ]]; then
  echo "Set R2_PREVIEW_REMOTE=previewcache:<private-bucket>[/prefix]" >&2; exit 3
fi
if [[ "${RCLONE_CONFIG_PREVIEWCACHE_TYPE:-}" != "s3" ||
      "${RCLONE_CONFIG_PREVIEWCACHE_PROVIDER:-}" != "Cloudflare" ||
      ! "${RCLONE_CONFIG_PREVIEWCACHE_ENDPOINT:-}" =~ ^https:// ||
      -z "${RCLONE_CONFIG_PREVIEWCACHE_ACCESS_KEY_ID:-}" ||
      -z "${RCLONE_CONFIG_PREVIEWCACHE_SECRET_ACCESS_KEY:-}" ]]; then
  echo "Private Cloudflare R2 S3 credentials/endpoint not configured" >&2; exit 4
fi
if [[ ! -d "$STAGE/previews" || ! -f "$STAGE/metadata/catalog.json" ]]; then
  echo "Missing preview staging data" >&2; exit 5
fi
python3 "$HERE/verify_r2_cache.py" "$STAGE"
# Guard total existing R2 usage conservatively; this cannot guarantee $0 fees
# because operation counts and other account usage are not available here.
CURRENT="$(rclone size "$REMOTE" --json)"
export CURRENT
python3 - "$STAGE" <<'PY'
import json,os,sys
from pathlib import Path
from verify_r2_cache import check_previews,MAX_CACHE_BYTES
stage=Path(sys.argv[1])
existing=json.loads(os.environ["CURRENT"])
remote_bytes=existing.get("bytes")
if type(remote_bytes) is not int or remote_bytes < 0:
    raise SystemExit("Cannot verify existing R2 cache quota")
stage_bytes=sum(size for _,size,_ in check_previews(stage))
if remote_bytes + stage_bytes > MAX_CACHE_BYTES:
    raise SystemExit("Conservative 8GB R2 guard exceeded (existing + entire batch)")
print("R2_PREUPLOAD_QUOTA_GUARD",remote_bytes,stage_bytes,flush=True)
PY
# Copy *only* the preview tree. Never recursively copy the whole staging area.
rclone copy "$STAGE/previews" "$REMOTE/previews" --transfers 3 --checkers 4 --retries 3
# Read back ALL R2 preview objects and verify by SHA256. Do not claim cache ready
# based on successful PUT, listing or object size alone.
python3 "$HERE/verify_r2_cache.py" "$STAGE" --verify-remote "$REMOTE"
echo "R2 private preview cache: uploaded and verified; originals remain in TeraBox"
