#!/usr/bin/env python3
"""No-provider, no-credential readiness regression for all 49 incident photos."""
import hashlib
import io
import json
import os
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("GALLERY_ACCESS_TOKEN","readiness-unit-only")
os.environ.setdefault("RCLONE_CONFIG_ARCHIVE_COOKIE","readiness-unit-only")
from gateway import main as gateway

sample=io.BytesIO()
Image.new("RGB",(32,48),(40,90,140)).save(sample,format="JPEG")
data=sample.getvalue()
sha=hashlib.sha256(data).hexdigest()
prior_mimmi=gateway._cache.copy()
prior_yui=gateway._yui_cache.copy()
prior_ttl=gateway._owner_rescue_until.copy()
prior_values=gateway._media_cache.values.copy()
prior_bytes=gateway._media_cache.bytes
try:
    with TestClient(gateway.app) as c:
        cold=c.get("/api/gallery-media-readiness")
        assert cold.status_code==200
        assert cold.json()["ready"] is False
        assert cold.json()["expected"]==56
        catalog_by_model={}
        for model,works in gateway._INCIDENT_MEDIA.items():
            albums=[]
            remote=gateway.REMOTE if model=="mimmi" else gateway.YUI_REMOTE
            for work,count in works:
                photos=[]
                for number in range(1,count+1):
                    key=f"originals/{work}/{number:05}.jpg"
                    photos.append({"number":number,"key":key,"bytes":len(data),"sha256":sha})
                    assert gateway._media_cache.insert_verified(remote,key,len(data),sha,data)
                albums.append({"id":work,"images":photos})
            catalog_by_model[model]={"schema_version":1,"model":model,"albums":albums}
        gateway._cache.update(catalog=catalog_by_model["mimmi"],time=time.time())
        gateway._yui_cache.update(catalog=catalog_by_model["yui"],time=time.time())
        gateway._owner_rescue_until.update(mimmi=time.time()+5400,yui=time.time()+5400)
        ready=c.get("/api/gallery-media-readiness")
        assert ready.status_code==200,ready.text
        assert ready.json()=={"ready":True,"available":56,"expected":56},ready.text
        assert ready.headers["cache-control"]=="no-store"
        # Even with 55 intact exact originals, one missing image fails the
        # whole gallery guarantee; check must never be misreported green.
        victim=gateway._media_cache.values.popitem()
        incomplete=c.get("/api/gallery-media-readiness")
        assert incomplete.json()["ready"] is False,incomplete.text
        assert incomplete.json()["available"]<56
        gateway._media_cache.values[victim[0]]=victim[1]
        gateway._owner_rescue_until["yui"]=time.time()+20
        expired=c.get("/api/gallery-media-readiness")
        assert expired.json()["ready"] is False,expired.text
        # No signed token, cookie or public image bytes may appear in GET.
        assert "sha256" not in ready.text
        assert "key" not in ready.text
        assert "cookie" not in ready.text
        print("GALLERY_BOTH_OWNER_ALL_56_ORIGINALS_READINESS_FAIL_CLOSED_PASS")
finally:
    gateway._cache.update(prior_mimmi)
    gateway._yui_cache.update(prior_yui)
    gateway._owner_rescue_until.update(prior_ttl)
    gateway._media_cache.values.clear()
    gateway._media_cache.values.update(prior_values)
    gateway._media_cache.bytes=prior_bytes
