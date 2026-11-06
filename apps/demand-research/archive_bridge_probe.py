"""One-shot aggregate TeraBox readback diagnostic, via the existing trusted Actions OIDC job.

No public account names, media, provider cookies or identity assertions are logged.
"""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE="https://intersection-originals-free.onrender.com"
AUDIENCE="intersection-originals-free/credential-v1"


def read_json(url,headers=None,timeout=95):
    request=Request(url,headers={"Accept":"application/json",**(headers or {})})
    with urlopen(request,timeout=timeout) as response:
        if response.status!=200:
            raise RuntimeError("Archive diagnostic request failed")
        return json.load(response)


def main():
    endpoint=os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    separator="&" if "?" in endpoint else "?"
    identity=read_json(endpoint+separator+urlencode({"audience":AUDIENCE}),
        headers={"Authorization":"bearer "+os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
        timeout=15)["value"]
    data=read_json(BASE+"/api/bridge/diagnostics",
                   headers={"Authorization":"Bearer "+identity},timeout=95)
    for key in ("automated_posts_state","automated_posts",
                "account_bundles_state","account_zip_candidates",
                "account_zip_read_verified","account_registry_state",
                "account_registry_count"):
        val=data.get(key)
        if isinstance(val,(str,int)) or val is None:
            print("INTERSECTION_ARCHIVE_AUDIT",key, val)
    if data.get("automated_posts_state")!="ok":
        raise SystemExit("Automated post original readback not verified")
    if data.get("account_bundles_state") in ("readback_failed","listing_failed"):
        raise SystemExit("Account ZIP readback not verified")


if __name__=="__main__":
    main()
