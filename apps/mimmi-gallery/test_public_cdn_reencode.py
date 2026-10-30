#!/usr/bin/env python3
"""No-network regression checks: old SHA mismatch must be explicitly opt-in."""
import hashlib
import io
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "yui-gallery"))
import collect_private_batch as mod


class FakeResponse:
    status_code = 200
    def __init__(self, raw):
        self.raw=raw
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size):
        yield self.raw


def main():
    rgb=Image.effect_noise((900,700),64).convert("RGB")
    out=io.BytesIO()
    rgb.save(out,format="JPEG",quality=83)
    raw=out.getvalue()
    assert len(raw)>50000, len(raw)
    base={
        "number":22,
        "url":"https://cdn.v2ph.com/photos/test-public-existing.jpg",
        "sha256":"a"*64,
        "bytes":int(len(raw)*1.07),
        "width":900,
        "height":700
    }
    source="https://www.v2ph.com/album/example.html"
    with patch.object(mod.requests,"get",return_value=FakeResponse(raw)):
        normal,err=mod.verify_one(base,source,allow_public_revision=False)
        assert normal is None and "mismatch" in err["reason"],err
        revised,err=mod.verify_one(base,source,allow_public_revision=True)
        assert err is None,err
        p,data=revised
        assert data==raw and p["sha256"]==hashlib.sha256(raw).hexdigest()
        assert p["bytes"]==len(raw) and p["public_source_reencoded"]
        assert p["url"].endswith(p["sha256"]+".jpg")
        gum=dict(base,url="https://public-files.gumroad.com/sample.webp")
        rejected,err=mod.verify_one(gum,source,allow_public_revision=True)
        assert rejected is None and "safe_revision_policy" in err["reason"],err
        wrong=dict(base,width=1000)
        rejected,err=mod.verify_one(wrong,source,allow_public_revision=True)
        assert rejected is None and "dimensions_mismatch" in err["reason"],err
        short=dict(base,bytes=len(raw)*4)
        rejected,err=mod.verify_one(short,source,allow_public_revision=True)
        assert rejected is None and "safe_revision_policy" in err["reason"],err
    assert not mod.safe_reencoded_public_preview(base,b"", "JPEG",900,700,base["url"])
    print("MIMMI_OPT_IN_CDN_IMAGE_RECOVERY_TEST_PASS",
          {"current_bytes":len(raw),"strict_sha_unchanged":True,
           "public_jpeg_reencode_accepted":True,"gumroad_small_preview_rejected":True})


if __name__=="__main__":
    main()
