#!/usr/bin/env python3
"""Direct-view end-to-end real TeraBox original/preview integrity test."""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

BASE=os.environ.get("PRIVATE_GATEWAY_TEST_BASE","http://127.0.0.1:18765").rstrip("/")
TOKEN=os.environ.get("GALLERY_ACCESS_TOKEN")

def fetch(path, auth=True, method="GET", headers=None):
    actual_headers={
        "Origin":"https://koith.github.io",
        "Cache-Control":"no-cache",
    }
    if auth and TOKEN:actual_headers["Authorization"]="Bearer "+TOKEN
    if headers:actual_headers.update(headers)
    request=urllib.request.Request(BASE+path,method=method,headers=actual_headers)
    try:
        with urllib.request.urlopen(request,timeout=110) as response:
            return response.status,{k.lower():v for k,v in response.headers.items()},response.read()
    except urllib.error.HTTPError as error:
        return error.code,{k.lower():v for k,v in error.headers.items()},error.read()

for model,route in (("yui","/api/yui"),("mimmi","/api")):
    status,_,body=fetch(route+"/catalog",auth=False)
    assert status==200,(model,"passwordless catalog unavailable",status)
    status,headers,body=fetch(route+"/catalog")
    assert status==200,(model,"authenticated catalog",status,body[:100])
    assert headers.get("access-control-allow-origin")=="https://koith.github.io"
    catalog=json.loads(body)
    assert catalog.get("model")==model and catalog.get("schema_version")==1
    assert isinstance(catalog.get("albums"),list)
    count=sum(len(a["images"]) for a in catalog["albums"])
    expected=2700 if model=="yui" else 2600
    assert count>=expected,(model,"missing many already stored originals",count)
    visited=[]
    for album in [catalog["albums"][0],catalog["albums"][-1]]:
        photo=album["images"][0]
        aid=album["id"];number=photo["number"]
        for kind in ("preview","original"):
            p=f"{route}/media/{aid}/{number}/{kind}"
            status,headers,blob=fetch(p)
            assert status==200,(model,kind,status,blob[:100])
            exp_size=photo.get("preview_bytes") if kind=="preview" else photo["bytes"]
            exp_sha=photo.get("preview_sha256") if kind=="preview" else photo["sha256"]
            if kind=="preview" and not photo.get("preview"):
                exp_size=photo["bytes"];exp_sha=photo["sha256"]
            assert len(blob)==exp_size,(model,kind,"wrong bytes",len(blob),exp_size)
            assert hashlib.sha256(blob).hexdigest()==exp_sha,(model,kind,"wrong sha256")
            assert headers.get("access-control-allow-origin")=="https://koith.github.io"
        visited.append(number)
    status,_,_=fetch(route+"/media/"+catalog["albums"][0]["id"]+"/"+str(catalog["albums"][0]["images"][0]["number"])+"/original",auth=False)
    assert status==200,(model,"passwordless original unavailable",status)
    print("PRIVATE_GALLERY_BROWSER_ORIGIN_REAL_TERABOX_BYTE_QA",
          json.dumps({"model":model,"actual_catalog_photos":count,
                      "real_originals_and_previews_shas_verified":4,
                      "auth_required":False,"cors_permitted":True,
                      "separate_model_namespace":True}),flush=True)
print("YUI_AND_MIMMI_END_TO_END_REAL_PASSWORDLESS_PHOTOS_PASS")
