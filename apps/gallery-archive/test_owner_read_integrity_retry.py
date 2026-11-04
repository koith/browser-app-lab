#!/usr/bin/env python3
"""Zero-network regression: deny corrupt originals and survive real restart races."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
import restore_known_owner_cache as recovery


source=io.BytesIO()
Image.new("RGB",(320,480),(44,99,127)).save(source,format="JPEG")
valid=source.getvalue()
photo={"sha256":hashlib.sha256(valid).hexdigest(),"bytes":len(valid),
       "width":320,"height":480}
def deny(code, detail):
    return HTTPError("http://localhost/ignored",code,"expected test",{},io.BytesIO(
        json.dumps({"detail":detail}).encode()))


with patch.object(recovery,"verified_file",side_effect=[b"truncated",valid]) as get,patch.object(
        recovery.time,"sleep") as sleep:
    result=recovery.verified_same_owner_existing_read(
        "yui","originals/known/001.jpg",{},photo,"original",attempts=2)
    assert result==valid and get.call_count==2
    sleep.assert_called_once()

with patch.object(recovery,"verified_file",return_value=b"wrong"*25) as get,patch.object(
        recovery.time,"sleep"):
    try:
        recovery.verified_same_owner_existing_read(
            "mimmi","originals/known/001.jpg",{},photo,"original",attempts=3)
    except recovery.OwnerReadUnavailable:
        pass
    else:
        raise AssertionError("Corrupt image accepted")
    assert get.call_count==3

with patch.object(recovery,"verified_file",side_effect=[
        b'{"error_code":31326,"error_msg":"anti hotlinking"}',valid]) as get,patch.object(
        recovery.time,"sleep"):
    try:
        recovery.verified_same_owner_existing_read(
            "yui","originals/known/001.jpg",{},photo,"original",attempts=3)
    except recovery.OwnerReadUnavailable:
        pass
    else:
        raise AssertionError("Explicit denial was bypassed")
    assert get.call_count==1

with patch.object(recovery,"verified_file",
                  side_effect=recovery.OwnerReadUnavailable("Provider denied")) as get:
    try:
        recovery.verified_same_owner_existing_read(
            "mimmi","originals/known/001.jpg",{},photo,"original",attempts=3)
    except recovery.OwnerReadUnavailable:
        pass
    else:
        raise AssertionError("Explicit provider exception ignored")
    assert get.call_count==1

headers={"X-Owner-Album":"known","X-Owner-Number":"1","X-Owner-Variant":"original"}
with patch.object(recovery,"send",side_effect=[
        deny(409,"Owner catalog is not verified"),
        {"verified":True},
        {"cached":True}
    ]) as send:
    reply=recovery.send_verified_photo_with_catalog_recovery(
        "yui",valid,"signed-token",headers,b'{"model":"yui"}')
    assert reply["cached"] is True
    assert [c.args[0] for c in send.call_args_list]==[
        "/internal/gallery-rescue-media/yui",
        "/internal/gallery-rescue-catalog/yui",
        "/internal/gallery-rescue-media/yui",
    ]
    assert send.call_args_list[0].args[1]==valid
    assert send.call_args_list[2].args[1]==valid

for code,detail in [(409,"Owner SHA mismatch"),(403,"Forbidden"),
                    (503,"Upstream denied")]:
    with patch.object(recovery,"send",side_effect=deny(code,detail)) as send:
        try:
            recovery.send_verified_photo_with_catalog_recovery(
                "mimmi",valid,"signed-token",headers,b"catalog")
        except HTTPError as err:
            assert err.code==code
        else:
            raise AssertionError("Unverified remote conflict retried")
        assert send.call_count==1
print("GALLERY_OWNER_SHA_RETRY_AND_RENDER_RESTART_FAIL_CLOSED_PASS")


# Wrong-model content on the same account can be a transient server response;
# do NOT publish it or use it across the two owner galleries.
good_catalog={"schema_version":1,"model":"mimmi","albums":[{"id":"known","images":[]}]}
with patch.object(recovery,"verified_file",side_effect=[
        b'{"schema_version":1,"model":"yui","albums":[{"id":"wrong"}]}',
        json.dumps(good_catalog).encode()
    ]) as get,patch.object(recovery.time,"sleep"):
    raw,data=recovery.verified_owner_catalog("mimmi",{},attempts=2)
    assert data["model"]=="mimmi" and get.call_count==2

for denied in [b'{"error_code":31326}',b'{"errno":400141}']:
    with patch.object(recovery,"verified_file",side_effect=[
            denied,json.dumps(good_catalog).encode()
        ]) as get:
        try:
            recovery.verified_owner_catalog("mimmi",{},attempts=3)
        except recovery.OwnerReadUnavailable:
            pass
        else:
            raise AssertionError("Explicit owner catalog rejection was retried")
        assert get.call_count==1

# Failed Yui owner authentication must not stop Mimmi's incident photos.
models=[]
def one_model(model,token):
    models.append(model)
    if model=="yui":
        raise recovery.OwnerReadUnavailable("First owner temporarily unavailable")
with patch.object(recovery,"run",side_effect=one_model),patch.object(
        recovery,"identity",return_value="signed-fixture"):
    try:
        recovery.main()
    except recovery.OwnerReadUnavailable as error:
        assert "yui" in str(error) and "mimmi" not in str(error)
    else:
        raise AssertionError("Partial owner recovery was claimed as full success")
    assert models==["yui","mimmi"]
print("GALLERY_FAIL_CLOSED_WRONG_OWNER_CATALOG_AND_INDEPENDENT_MODELS_PASS")
