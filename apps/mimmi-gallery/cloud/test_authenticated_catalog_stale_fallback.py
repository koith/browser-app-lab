#!/usr/bin/env python3
"""No-network regression: verified owner catalogs survive refresh and 503.

Only previously verified metadata may be retained. Unknown owners or unverified
catalogs fail closed; photos remain separately SHA checked on every read.
"""
import asyncio
import json
import os
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

os.environ["GALLERY_ACCESS_TOKEN"]="test-token"
os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]="test-original-cookie"
from gateway import main as gw

originals={
    "mimmi":(dict(gw._cache),gw._owner_rescue_until["mimmi"]),
    "yui":(dict(gw._yui_cache),gw._owner_rescue_until["yui"]),
}
prior_cookie=gw.COOKIE
old_environment={
    "RCLONE_CONFIG_ARCHIVE_COOKIE":os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"),
    "RCLONE_CONFIG_ARCHIVE_YUI_COOKIE":os.environ.get("RCLONE_CONFIG_ARCHIVE_YUI_COOKIE"),
}
def snapshot(model,marker):
    return {
        "schema_version":1,"model":model,
        "storage":"owner-private-terabox-sha-verified-bytes",
        "albums":[{"id":"snapshot-"+model,"title":marker,"images":[{
          "number":1,"key":"originals/snapshot-"+model+"/00001.jpg",
          "sha256":"a"*64,"bytes":500,"width":320,"height":480
        }]}]
    }
async def offline(*args,**kwargs):
    raise HTTPException(status_code=503,detail="Provider denied")

try:
    # A prior authenticated catalog must survive a transient 503 even if its
    # usual 180-second refresh TTL has expired.
    for model in ("mimmi","yui"):
        state=gw._cache if model=="mimmi" else gw._yui_cache
        load=gw.get_catalog if model=="mimmi" else gw.yui_catalog_bytes
        initial=snapshot(model,"signed-prior")
        state.update(catalog=initial,time=0)
        gw._owner_rescue_until[model]=0
        with patch.object(gw,"rclone_bytes",side_effect=offline):
            assert asyncio.run(load()) is initial,model
        state.update(catalog=None,time=0)
        with patch.object(gw,"rclone_bytes",side_effect=offline):
            try:asyncio.run(load())
            except HTTPException as ex:assert ex.status_code==503
            else:raise AssertionError("Unknown catalog was silently substituted")
        print("AUTHENTICATED_CATALOG_STALE_ON_503_NOT_EMPTY_PASS",model)

    # Session refresh is the old destructive path. It must replace its cache
    # with the newly verified owner's actual manifest, never set catalog=None.
    async def valid_remote(path,limit,remote=None,cookie_override=None):
        assert path=="metadata/catalog.json",path
        assert cookie_override in ("verified-mimmi-cookie","verified-yui-cookie")
        model="yui" if remote==gw.YUI_REMOTE else "mimmi"
        assert cookie_override==("verified-"+model+"-cookie")
        return json.dumps(snapshot(model,"new-owner-verified")).encode()
    with patch.object(gw,"_verify_sync_identity",return_value=True),patch.object(
        gw,"rclone_bytes",side_effect=valid_remote):
        with TestClient(gw.app) as app:
            res=app.post("/internal/terabox-session-refresh",
              headers={"Authorization":"Bearer test-signed-token"},
              json={"cookie":"verified-mimmi-cookie",
                    "yui_cookie":"verified-yui-cookie"})
            assert res.status_code==200,res.text[:180]
            assert res.json()["synced"] is True
    for model in ("mimmi","yui"):
        state=gw._cache if model=="mimmi" else gw._yui_cache
        assert state["catalog"]["albums"][0]["title"]=="new-owner-verified",model
        assert gw._owner_rescue_until[model]>time.time()+5300,model
        state["time"]=0
        gw._owner_rescue_until[model]=0
        with patch.object(gw,"rclone_bytes",side_effect=offline):
            load=gw.get_catalog if model=="mimmi" else gw.yui_catalog_bytes
            assert asyncio.run(load())["albums"][0]["title"]=="new-owner-verified"
    print("SIGNED_SESSION_REFRESH_PRESERVES_BOTH_OWNER_MANIFESTS_PASS")

    # Malformed/wrong-owner metadata is not accepted as a replacement.
    for model in ("mimmi","yui"):
        state=gw._cache if model=="mimmi" else gw._yui_cache
        state.update(catalog=snapshot(model,"valid"),time=0)
        gw._owner_rescue_until[model]=0
        async def wrong(*args,**kwargs):
            return json.dumps(snapshot("foreign","wrong")).encode()
        with patch.object(gw,"rclone_bytes",side_effect=wrong):
            try:asyncio.run(gw.get_catalog() if model=="mimmi" else gw.yui_catalog_bytes())
            except HTTPException as ex:assert ex.status_code==502,model
            else:raise AssertionError("Wrong owner metadata accepted")
        assert state["catalog"]["albums"][0]["title"]=="valid"
    print("WRONG_OWNER_CATALOG_NOT_ACCEPTED_OR_OVERWRITTEN_PASS")
finally:
    gw.COOKIE=prior_cookie
    for model,(snap,until) in originals.items():
        state=gw._cache if model=="mimmi" else gw._yui_cache
        state.clear();state.update(snap)
        gw._owner_rescue_until[model]=until
    for key,value in old_environment.items():
        if value is None:os.environ.pop(key,None)
        else:os.environ[key]=value
