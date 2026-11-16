"""Re-enqueue every independently SHA-verified public SNS account for
append-only capture of its biography, cover, profile image and public posts.

Runs only inside the trusted, authorized GitHub Actions job. No raw account
list, credential, private archive object or encrypted bytes are committed or
printed. An accepted dispatch is NOT a verified stored snapshot.
"""
from __future__ import annotations

import json
import os
import time
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from verified_bundle_reader import BundleAccountCloud
from target_account_enrichment import PROFILE_FILE_RE

import github_temp_bundle
from target_account_archive import profile_input

TARGET_WORKFLOW="intersection-target-account-bundle.yml"
TARGET_REPO="koith/browser-app-lab"
MAX_RELEASES_TO_VERIFY=100
MAX_ACCOUNTS=40


def saved_accounts(bundles):
    """Newest signed account-bound profile registration per unique account."""
    selected={}
    for bundle in bundles:
        if bundle.account in selected:
            continue
        entry=bundle.accounts.get(bundle.account)
        if not isinstance(entry,dict):
            continue
        platform=entry.get("platform")
        url=entry.get("profile_url")
        if platform not in ("bluesky","mastodon") or not isinstance(url,str):
            continue
        try:
            profile_input(platform,url)
        except (ValueError,TypeError):
            continue
        if len(selected)>=MAX_ACCOUNTS:
            raise RuntimeError("verified account inventory exceeds safe one-shot bound")
        tag=getattr(bundle,"archive_tag",None)
        if not isinstance(tag,str) or not github_temp_bundle.TAG.fullmatch(tag):
            raise RuntimeError("Selected verified archive has no exact signed release tag")
        run_id=int(github_temp_bundle.TAG.fullmatch(tag).group(1))
        # Every field comes from the very same AES/SHA-verified private ZIP.
        # Metadata from another account or a live unverified API is refused.
        details={"display_name":"","handle":""}
        try:
            archive=BundleAccountCloud(bundle)
            names=sorted((n for n in archive.names("profile/snapshots")
                          if PROFILE_FILE_RE.fullmatch(n)),reverse=True)
            for name in names[:4]:
                raw=archive.read("profile/snapshots/"+name,cap=300000,optional=True)
                if not raw:continue
                document=json.loads(raw)
                if (isinstance(document,dict) and
                    document.get("platform")==platform and
                    document.get("identity")==entry.get("identity")):
                    details["display_name"]=str(document.get("display_name") or "")[:140]
                    details["handle"]=str(document.get("handle") or "")[:220]
                    break
        except (RuntimeError,ValueError,TypeError,KeyError):
            pass
        selected[bundle.account]={
            "platform":platform,"account":url,
            "index_row":{
                "account_key":bundle.account,"platform":platform,
                "release_tag":tag,"workflow_run_id":run_id,
                "profile_url":url,"display_name":details["display_name"],
                "handle":details["handle"],
                "recorded_at":str(bundle.recorded_at or "")[:70],
                "posts_verified":int(bundle.post_count),
                "objects_verified":int(bundle.object_count)}}
    return list(selected.values())


def dispatch_one(selected,token):
    if not isinstance(token,str) or len(token)<20:
        raise RuntimeError("authorized GitHub Actions token unavailable")
    payload={"ref":"main","inputs":{
        "platform":selected["platform"],
        "account":selected["account"],
        # This is a small incremental profile/metadata repair, not a
        # destructive recrawl of old stored posts.
        "max_pages":"1"}}
    url=("https://api.github.com/repos/"+TARGET_REPO+
         "/actions/workflows/"+TARGET_WORKFLOW+"/dispatches")
    request=Request(url,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                    method="POST",headers={
        "Accept":"application/vnd.github+json",
        "Content-Type":"application/json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"intersection-verified-public-profile-backfill",
        "Authorization":"Bearer "+token})
    with urlopen(request,timeout=30) as response:
        if response.status!=204:
            raise RuntimeError("GitHub did not accept profile backup dispatch")
    return True


def import_durable_index(accounts):
    if not 1<=len(accounts)<=MAX_ACCOUNTS:
        raise RuntimeError("Invalid signed account inventory size")
    endpoint=os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    secret=os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
    proof_url=endpoint+("&" if "?" in endpoint else "?")+urlencode({
        "audience":"intersection-originals-free/credential-v1"})
    proof=Request(proof_url,headers={"Authorization":"Bearer "+secret})
    with urlopen(proof,timeout=15) as response:
        jwt=json.loads(response.read(16000)).get("value")
    if not isinstance(jwt,str) or len(jwt)<100:
        raise RuntimeError("Trusted GitHub archive inventory identity unavailable")
    destination="https://intersection-originals-free.onrender.com/api/bridge/archive-index"
    body=json.dumps({"rows":[item["index_row"] for item in accounts]},
                    sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    req=Request(destination,data=body,method="POST",headers={
        "Authorization":"Bearer "+jwt,
        "Content-Type":"application/json",
        "Accept":"application/json",
        "User-Agent":"intersection-archive-verification-inventory-v1"})
    with urlopen(req,timeout=180) as response:
        if response.status!=200:
            raise RuntimeError("Signed durable archive inventory rejected")
        result=json.loads(response.read(10000))
    if result.get("accepted") is not True or result.get("stored")!=len(accounts):
        raise RuntimeError("Durable account inventory independent readback failed")
    print("PUBLIC_PROFILE_SIGNED_DURABLE_INDEX",
          json.dumps({"indexed":len(accounts),"verified_from_zip":True}),
          flush=True)


def main():
    if os.getenv("GITHUB_REPOSITORY")!=TARGET_REPO:
        raise RuntimeError("trusted repository context required")
    if os.getenv("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("main branch is required to restore public profiles")
    token=os.getenv("GITHUB_TOKEN","")
    # Inventory is independently AES-GCM decrypted, whole ZIP SHA checked,
    # and bound to exact platform/actor; no unverified list can dispatch.
    accounts=saved_accounts(github_temp_bundle.workflow_verified_bundles(
        max_scan=MAX_RELEASES_TO_VERIFY))
    if not accounts:
        raise RuntimeError("no verified archived public profiles to restore")
    print("PUBLIC_PROFILE_BACKFILL_INVENTORY",
          json.dumps({"accounts":len(accounts),
                      "release_scan_limit":MAX_RELEASES_TO_VERIFY}),
          flush=True)
    import_durable_index(accounts)
    if os.getenv("PROFILE_INDEX_ONLY","").lower() in ("true","1"):
        print("PUBLIC_PROFILE_INDEX_ONLY_COMPLETE",
              json.dumps({"accounts":len(accounts),"captures_dispatched":0}),
              flush=True)
        return
    accepted=0
    for item in accounts:
        # Do not print account names, URLs, profile descriptions or tokens.
        # The source SNS API remains the gate for current-public records.
        dispatch_one(item,token)
        accepted+=1
        print("PUBLIC_PROFILE_BACKFILL_DISPATCH",
              json.dumps({"accepted":accepted,"total":len(accounts)}),
              flush=True)
        time.sleep(.8)
    print("PUBLIC_PROFILE_BACKFILL_ACCEPTED",
          json.dumps({"accepted":accepted,"source_verified_storage":0,
                      "note":"dispatch_only"}),
          flush=True)


if __name__=="__main__":
    main()
