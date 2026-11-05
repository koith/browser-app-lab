#!/usr/bin/env python3
"""Cheap authenticated-catalog RAM health probe with no photo transfers.

One GET to a public health boolean. Only same-repo signed owner workflows
can perform recovery, and neither this probe nor its response exposes media.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL="https://mimmi-private-gallery-free.onrender.com/api/gallery-media-readiness"


def check() -> bool:
    try:
        with urlopen(Request(URL,headers={
            "User-Agent":"Gallery-Owned-Cache-Survival/1",
            "Cache-Control":"no-store",
        }),timeout=75) as response:
            if response.status != 200:
                return False
            data=json.load(response)
            return (type(data) is dict and data.get("ready") is True and
                type(data.get("expected")) is int and data["expected"]==56
                and data.get("available")==56)
    except (HTTPError, URLError, TimeoutError, ValueError, TypeError, OSError):
        return False


if __name__=="__main__":
    if check():
        print("BOTH_OWNER_GALLERIES_ALL_56_USER_REPORTED_ORIGINALS_STILL_AVAILABLE")
    else:
        print("OWNER_GALLERY_FULL_56_ORIGINALS_READBACK_REQUIRED")
        raise SystemExit(11)
