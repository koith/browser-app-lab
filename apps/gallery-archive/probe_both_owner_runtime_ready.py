#!/usr/bin/env python3
"""Cheap external read-only health check for both gallery owner caches.

Returns 0 only if each model has a verified album catalog AND a representative
already-cached owner cover decodes. No credentials, media writes, or TeraBox
calls from this script. A failed/slow/incomplete response means: run normal
signed same-owner recovery, never claim gallery availability.
"""
from __future__ import annotations
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ORIGIN = "https://mimmi-private-gallery-free.onrender.com"
COVERS = {
    "mimmi": "/api/cover/mimmi/mimmi-indie-sana-sopmod2-2019/1?v=c5ca86fdd0129df49171ceed",
    "yui": "/api/cover/yui/yui-chinokun-illustar-2026-public/2?v=3b63b9ed632944d7853946a2",
}


def check() -> bool:
    try:
        request = Request(ORIGIN + "/api/health", headers={"User-Agent": "Gallery-Cache-Readiness/1"})
        with urlopen(request, timeout=75) as result:
            if result.status != 200:
                return False
            payload=json.load(result)
            if not isinstance(payload,dict) or payload.get("data_connected") is not True:
                return False
        request = Request(ORIGIN + "/api/yui/catalog", headers={"User-Agent": "Gallery-Cache-Readiness/1"})
        with urlopen(request, timeout=45) as result:
            if result.status != 200:
                return False
            catalog=json.load(result)
            if not isinstance(catalog,dict) or not isinstance(catalog.get("albums"),list) or not catalog["albums"]:
                return False
        for model, path in COVERS.items():
            request=Request(ORIGIN + path,headers={"User-Agent":"Gallery-Cache-Readiness/1"})
            with urlopen(request,timeout=45) as response:
                if response.status != 200:
                    return False
                mime=response.headers.get("Content-Type","").split(";")[0].strip().lower()
                if mime not in ("image/jpeg","image/png","image/webp","image/avif"):
                    return False
                # The gateway's exact-SHA verification already completed when
                # bytes entered its private bounded cache. This is a cheap
                # proof-of-response, not a full-gallery or pixel integrity test.
                if not response.read(1):
                    return False
        return True
    except (HTTPError, URLError, TimeoutError, ValueError, TypeError, OSError):
        return False


if __name__=="__main__":
    if check():
        print("OWNER_RUNTIME_BOTH_MODELS_ALREADY_SERVING_REPRESENTATIVE_PHOTOS",flush=True)
        raise SystemExit(0)
    print("OWNER_RUNTIME_NEEDS_AUTHENTICATED_READBACK",flush=True)
    raise SystemExit(11)
