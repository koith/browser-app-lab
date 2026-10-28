#!/usr/bin/env bash
set -euo pipefail
python -m pip install 'requests==2.32.5' 'Pillow==11.3.0'
python -m py_compile apps/mimmi-gallery/download_public_images_private.py apps/mimmi-gallery/cloud/*.py
python apps/mimmi-gallery/test_private_download.py
python apps/mimmi-gallery/cloud/test_stage_private_archive.py
python -m pip install -r apps/mimmi-gallery/cloud/gateway/requirements.txt 'httpx==0.28.1'
python apps/mimmi-gallery/cloud/test_gateway.py

if [[ -z "${RCLONE_CONFIG_ARCHIVE_COOKIE:-}" ]]; then
  echo "::notice::MIMMI_PRIVATE_CLOUD_NOT_CONNECTED: no approved personal TeraBox session configured"
  echo "MIMMI_PRIVATE_CLOUD_RESULT=NOT_CONNECTED" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
  exit 0
fi

export RCLONE_CONFIG_ARCHIVE_TYPE=terabox
export ARCHIVE_REMOTE="archive:MimmiArchive"
export PRIVATE_DOWNLOAD_DIR="${RUNNER_TEMP:?}/mimmi-private-download"
export PRIVATE_STAGE_DIR="${RUNNER_TEMP:?}/mimmi-stage"
curl -fsSL https://github.com/gulp79/rclone-extra/releases/download/v1.75.2-extra/rclone-linux-amd64.zip -o /tmp/mimmi-rclone.zip
echo "78855325a2a8d83b3feee3a8363d32e1211babbf4cda6356fa8ca5f472075062  /tmp/mimmi-rclone.zip" | sha256sum -c -
mkdir -p /tmp/mimmi-rclone-bin
unzip -q /tmp/mimmi-rclone.zip -d /tmp/mimmi-rclone-bin
find /tmp/mimmi-rclone-bin -type f -name rclone -exec sudo install -m 755 {} /usr/local/bin/rclone \;
rclone listremotes | grep -qx 'archive:'

python apps/mimmi-gallery/download_public_images_private.py --output-dir "$PRIVATE_DOWNLOAD_DIR" --limit 0
mkdir -p "$PRIVATE_STAGE_DIR/originals"
rclone mkdir "$ARCHIVE_REMOTE/metadata"
rclone lsf "$ARCHIVE_REMOTE/metadata" --files-only > "$RUNNER_TEMP/mimmi-meta-files.txt"
if grep -qx 'catalog.json' "$RUNNER_TEMP/mimmi-meta-files.txt"; then
  rclone cat "$ARCHIVE_REMOTE/metadata/catalog.json" > "$RUNNER_TEMP/mimmi-previous-catalog.json"
  python - "$RUNNER_TEMP/mimmi-previous-catalog.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
assert d.get("model")=="mimmi" and d.get("schema_version")==1,"wrong private archive"
print("MIMMI_PREVIOUS_PRIVATE_ALBUMS",len(d.get("albums",[])))
PY
else
  : > "$RUNNER_TEMP/mimmi-previous-catalog.json"
fi
python apps/mimmi-gallery/cloud/stage_private_archive.py \
 --source apps/mimmi-gallery/source-viewer-albums.json \
 --private "$PRIVATE_DOWNLOAD_DIR" \
 --out "$PRIVATE_STAGE_DIR" \
 --previous "$RUNNER_TEMP/mimmi-previous-catalog.json"

rclone copy "$PRIVATE_STAGE_DIR/originals" "$ARCHIVE_REMOTE/originals" \
 --ignore-existing --transfers 3 --checkers 4 --retries 3 --timeout=60s
python apps/mimmi-gallery/cloud/verify_private_cloud.py \
 --stage "$PRIVATE_STAGE_DIR" --remote "$ARCHIVE_REMOTE" --mode media

# Publish only AFTER exact uploaded media bytes have passed remote readback.
rclone copyto "$PRIVATE_STAGE_DIR/metadata/catalog.json" "$ARCHIVE_REMOTE/metadata/catalog.json"
python apps/mimmi-gallery/cloud/verify_private_cloud.py \
 --stage "$PRIVATE_STAGE_DIR" --remote "$ARCHIVE_REMOTE" --mode catalog
python - <<'PY'
import json,os
from pathlib import Path
r=json.loads((Path(os.environ["PRIVATE_STAGE_DIR"])/"metadata/catalog.json").read_text(encoding="utf-8"))
count=r["summary"]["private_photo_records"]
assert count>0
print("MIMMI_PRIVATE_CLOUD_SHA_VERIFIED_PHOTOS",count)
with open(os.environ.get("GITHUB_STEP_SUMMARY","/dev/null"),"a") as f:
    f.write("MIMMI_PRIVATE_CLOUD_SHA_VERIFIED_PHOTOS="+str(count)+"\n")
PY
