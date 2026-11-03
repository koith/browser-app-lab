#!/usr/bin/env python3
"""Read-only live original-vs-ledger diagnosis for the Yui v04 gallery mismatch.

No cookie, token, private path, or image bytes are logged or persisted.
A public first-party GET is identical to the existing Pages lightbox action.
"""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import requests
from PIL import Image

BASE=Path(__file__).resolve().parents[2]/"apps/yui-gallery"
catalog=json.loads((BASE/"owner-index.json").read_text(encoding="utf-8"))
local=json.loads((BASE/"stored-albums.json").read_text(encoding="utf-8"))
assert catalog["model"]=="yui"
entry=next(a for a in catalog["albums"] if a["id"]=="v04")
assert len(entry["images"])==1
photo=entry["images"][0]
number=photo["number"]
assert number==1 and len(photo["sha256"])==64
version=photo["sha256"]
url="https://mimmi-private-gallery-free.onrender.com/api/yui/media/v04/1/original?v="+version
def characteristics(raw):
    with Image.open(BytesIO(raw)) as image:
        image.load()
        return {"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
                "width":image.width,"height":image.height,"format":image.format}

local_first=next(a for a in local["albums"] if a["id"]=="v04")["images"][0]
disk=BASE/local_first["url"]
assert disk.is_file()
stored=characteristics(disk.read_bytes())
assert stored["sha256"]==local_first["sha256"] and stored["bytes"]==local_first["bytes"]
assert [stored["width"],stored["height"]]==[local_first["width"],local_first["height"]]
print("YUI_V04_STATIC_PHYSICAL",json.dumps({
    "image_number":1,"dimensions":[stored["width"],stored["height"]],
    "sha_matches":True,"bytes":stored["bytes"]}),flush=True)

response=requests.get(url,timeout=(12,65),headers={
    "User-Agent":"ArchiveReadOnlyQA/1.0",
    "Accept":"image/jpeg,image/png,image/webp,image/*"
},allow_redirects=False)
print("YUI_V04_OWNER_GATEWAY_STATUS",json.dumps({
    "status":response.status_code,
    "mime":response.headers.get("Content-Type","").split(";")[0],
    "bytes":len(response.content)}),flush=True)
assert response.status_code==200, "Owner original must be readable through normal public gallery route"
assert response.headers.get("Content-Type","").startswith("image/")
raw=characteristics(response.content)
out={"recorded_dimensions":[photo["width"],photo["height"]],
     "actual_dimensions":[raw["width"],raw["height"]],
     "recorded_bytes":photo["bytes"],"actual_bytes":raw["bytes"],
     "sha256_matches_index":raw["sha256"]==photo["sha256"],
     "file_bytes_match_index":raw["bytes"]==photo["bytes"],
     "dimensions_match_index":[raw["width"],raw["height"]]==[photo["width"],photo["height"]]}
print("YUI_V04_OWNER_ORIGINAL_PHYSICAL_DIAGNOSTIC",json.dumps(out),flush=True)
assert out["sha256_matches_index"] and out["file_bytes_match_index"],(
    "Original gateway violated SHA-256/byte pin; do not replace with previews")
# Dimension mismatch is intentionally reported as evidence, not made PASS.
# Its fix must be a separate, evidence-backed correction of the exact record.
