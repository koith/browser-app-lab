#!/usr/bin/env python3
"""No-network regression for signed existing-owner photo rescue to private RAM."""
import hashlib
import io
import os
from unittest.mock import patch

os.environ["GALLERY_ACCESS_TOKEN"] = "offline-rescue-token"
os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"] = "offline-rescue-cookie"
from fastapi.testclient import TestClient
from PIL import Image
from gateway import main as gateway


def make_image():
    stream = io.BytesIO()
    Image.new("RGB", (380, 540), (32, 80, 125)).save(stream, format="JPEG")
    return stream.getvalue()


blob = make_image()
sha = hashlib.sha256(blob).hexdigest()
header = {"Authorization":"Bearer signed-offline-OIDC"}
with patch.object(gateway, "_verify_sync_identity",
                  side_effect=lambda value,workflow: (
                      value=="signed-offline-OIDC" and workflow==gateway._SYNC_WORKFLOW)):
    with TestClient(gateway.app) as client:
        for model in ("mimmi", "yui"):
            key=f"originals/test-{model}/00001.jpg"
            catalog={"schema_version":1,"model":model,"albums":[{
                "id":"test-"+model,"images":[{
                    "number":1,"key":key,"bytes":len(blob),
                    "sha256":sha,"width":380,"height":540
                }]
            }]}
            endpoint="/internal/gallery-rescue-catalog/"+model
            assert client.post(endpoint,content=b"{}",headers={}).status_code==403
            wrong=dict(catalog,model="foreign")
            assert client.post(endpoint,headers=header,json=wrong).status_code==422
            reply=client.post(endpoint,headers=header,json=catalog)
            assert reply.status_code==200,reply.text
            assert reply.json()["verified"] is True

            img_endpoint="/internal/gallery-rescue-media/"+model
            h={**header,"X-Owner-Album":"test-"+model,
               "X-Owner-Number":"1","X-Owner-Variant":"original"}
            assert client.post(img_endpoint,content=b"bad photo",headers=h).status_code==422
            assert client.post(img_endpoint,content=blob,headers={
                **h,"Authorization":"Bearer wrong"
            }).status_code==403
            assert client.post(img_endpoint,content=blob,headers={
                **h,"X-Owner-Album":"test-unrelated"
            }).status_code==404
            result=client.post(img_endpoint,content=blob,headers=h)
            assert result.status_code==200,result.text
            assert result.json()["cached"] is True
            path=("/api/yui" if model=="yui" else "/api")+(
                "/media/test-"+model+"/1/original?v="+sha)
            found=client.get(path)
            assert found.status_code==200,(model,found.status_code,found.text[:80])
            assert found.content==blob
            assert hashlib.sha256(found.content).hexdigest()==sha
            assert found.headers["content-type"].startswith("image/jpeg")
            gateway._media_cache.clear()
            gateway._owner_rescue_until[model]=0
            state=gateway._cache if model=="mimmi" else gateway._yui_cache
            state.update(catalog=None,time=0.0)
            print("BOTH_OWNER_MODELS_OIDC_SHA_RESCUE_RUNTIME_PASS",model)
print("VERIFIED_PRIVATE_MEDIA_RESCUE_NO_PROVIDER_BYPASS_PASS")
