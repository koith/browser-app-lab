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
from urllib.request import Request, urlopen

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
        selected[bundle.account]={"platform":platform,"account":url}
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
