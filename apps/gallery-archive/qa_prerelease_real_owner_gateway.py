#!/usr/bin/env python3
"""Pre-release gate: actual owned original bytes through candidate FastAPI ASGI.

Read existing photos with their designated owner account; never download new
sources, upload to TeraBox, publish media to GitHub, or modify production.
Test both original and preview URL while gateway's direct egress is denied.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(ROOT/"mimmi-gallery"/"cloud"))
from restore_known_owner_cache import verified_owner_catalog, verified_same_owner_existing_read
from gateway.cookie_format import cookie_header

TARGET={
    "mimmi": ("mimmi-indie-sana-sopmod2-2019",7),
    "yui": ("yui-chinokun-illustar-2026-public",4),
}

def run(model):
    value=os.environ.get("MIMMI_COOKIE" if model=="mimmi" else "YUI_COOKIE","")
    if len(value)<8:raise AssertionError("Owner account secret missing")
    env=os.environ.copy()
    env["RCLONE_CONFIG_ARCHIVE_TYPE"]="terabox"
    env["RCLONE_CONFIG_ARCHIVE_COOKIE"]=cookie_header(value)
    env.pop("RCLONE_CONFIG_ARCHIVE_DOMAIN",None)
    remote="archive:MimmiArchive" if model=="mimmi" else "archive:YuiArchive"
    os.environ.setdefault("GALLERY_ACCESS_TOKEN","staging-only-access-token")
    os.environ.setdefault("RCLONE_CONFIG_ARCHIVE_COOKIE","staging-gateway-unused")
    from gateway import main as gateway
    album_id,expected=TARGET[model]
    signature={"Authorization":"Bearer staging-verified-identity"}
    with tempfile.TemporaryDirectory(prefix="gallery-prerelease-") as directory:
        out=Path(directory)
        # Stage the exact same bounded, same-account reader used by the
        # production rescue, not a weaker one-attempt diagnostic.
        raw,catalog=verified_owner_catalog(model,env,attempts=3)
        assert catalog.get("model")==model and catalog.get("schema_version")==1
        album=next((a for a in catalog["albums"] if a.get("id")==album_id),None)
        assert album is not None,(model,"screenshot work absent")
        photos=sorted(album["images"],key=lambda p:p["number"])
        assert len(photos)==expected,(model,"incident album incomplete",len(photos))
        async def blocked_provider(*args,**kwargs):
            raise HTTPException(503,"Owner storage provider denied access",
                headers={"X-Archive-Read-Cause":"provider_denial"})
        with patch.object(gateway,"_verify_sync_identity",
                side_effect=lambda token,workflow:token=="staging-verified-identity" and workflow==gateway._SYNC_WORKFLOW),patch.object(
                gateway,"rclone_bytes",side_effect=blocked_provider):
            with TestClient(gateway.app) as client:
                response=client.post("/internal/gallery-rescue-catalog/"+model,
                                     headers=signature,content=raw)
                assert response.status_code==200,(model,"catalog stage HTTP",response.status_code)
                tested_preview=0;tested_cover=0
                for p in photos:
                    n=p["number"]
                    path=p.get("key","")
                    assert isinstance(path,str) and path.startswith("originals/"+album_id+"/")
                    # Three bounded same-account attempts handle transient
                    # incomplete content; explicit provider access denial is
                    # never retried and a wrong SHA is never accepted.
                    data=verified_same_owner_existing_read(
                        model,path,env,p,"original",attempts=3)
                    assert len(data)==p["bytes"]
                    assert hashlib.sha256(data).hexdigest()==p["sha256"]
                    with Image.open(io.BytesIO(data)) as img:
                        img.verify()
                        assert img.width==p["width"] and img.height==p["height"]
                    headers={**signature,"X-Owner-Album":album_id,
                             "X-Owner-Number":str(n),"X-Owner-Variant":"original"}
                    response=client.post("/internal/gallery-rescue-media/"+model,
                                         headers=headers,content=data)
                    assert response.status_code==200,(model,n,"stage original import",response.status_code)
                    prefix="/api/yui" if model=="yui" else "/api"
                    original=client.get(prefix+"/media/"+album_id+"/"+str(n)+"/original?v="+p["sha256"])
                    assert original.status_code==200,(model,n,"stage original HTTP",original.status_code)
                    assert original.content==data
                    assert hashlib.sha256(original.content).hexdigest()==p["sha256"]
                    assert original.headers["content-type"].startswith("image/")
                    if p.get("preview"):
                        sha=p.get("preview_sha256")
                        assert sha and len(sha)==64
                        preview=client.get(prefix+"/media/"+album_id+"/"+str(n)+"/preview?v="+sha)
                        # A denied preview must fall back to independently
                        # SHA-verified *original* already cached in staging.
                        assert preview.status_code==200,(model,n,"preview rejected instead of verified original",preview.status_code)
                        assert hashlib.sha256(preview.content).hexdigest()==p["sha256"]
                        assert preview.headers.get("X-Archive-Variant")=="verified-original-fallback"
                        tested_preview+=1
                    if tested_cover==0:
                        version=(p.get("preview_sha256") or p["sha256"])[:24]
                        cover=client.get("/api/cover/"+model+"/"+album_id+"/"+str(n)+"?v="+version)
                        assert cover.status_code==200,(model,n,"cover not decoded",cover.status_code)
                        with Image.open(io.BytesIO(cover.content)) as im:
                            im.verify()
                        tested_cover+=1
                assert tested_cover>=1
                assert tested_preview>=1,(model,"no incident preview path tested")
                print("GALLERY_PRERELEASE_OWNER_BYTE_TO_VIEWER_PASS",json.dumps({
                    "model":model,"incident_album_photos":len(photos),
                    "original_http_sha_verified":len(photos),
                    "denied_preview_to_original_verified":tested_preview,
                    "album_cover_decoded":tested_cover,
                    "real_private_owner_bytes":True,
                    "stage_only":True,
                    "render_deployed":False,
                    "physical_iphone_tested":False
                }),flush=True)
                gateway._media_cache.clear()
                gateway._owner_rescue_until[model]=0
                state=gateway._cache if model=="mimmi" else gateway._yui_cache
                state.update(catalog=None,time=0.0)
if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--model",required=True,choices=["mimmi","yui"])
    run(a.parse_args().model)
