"""Run inside a trusted GitHub Actions job, never in a browser.

The short-lived GITHUB_TOKEN is sent only to api.github.com. The Render
endpoint receives only a GitHub-signed OIDC identity assertion. Never log
access tokens or public account identifiers.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GATEWAY="https://intersection-originals-free.onrender.com"
GITHUB="https://api.github.com/repos/koith/browser-app-lab"
AUDIENCE="intersection-originals-free/credential-v1"


def request_json(url, *, headers=None, payload=None, timeout=90):
    encoded=json.dumps(payload).encode("utf-8") if payload is not None else None
    req=Request(url,data=encoded,method="POST" if encoded is not None else "GET",
                headers={"Accept":"application/json",**(headers or {})})
    with urlopen(req,timeout=timeout) as resp:
        if resp.status!=200:
            raise RuntimeError("Private queue operation not confirmed")
        return json.load(resp)


def oidc_assertion():
    endpoint=os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    separator="&" if "?" in endpoint else "?"
    result=request_json(endpoint+separator+urlencode({"audience":AUDIENCE}),
        headers={"Authorization":"bearer "+os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
        timeout=15)
    token=result.get("value")
    if not isinstance(token,str) or len(token)<100:
        raise RuntimeError("Missing GitHub OIDC identity")
    return token


def poll_once():
    jwt=oidc_assertion()
    bridge_headers={"Authorization":"Bearer "+jwt}
    if os.getenv("GITHUB_EVENT_NAME")=="push":
        # One-shot diagnostic after main code changes; never during the
        # five-minute credential refresh. Only aggregate counts are logged.
        try:
            snapshot=request_json(GATEWAY+"/api/bridge/diagnostics",
                                  headers=bridge_headers,timeout=90)
            for field in ("automated_posts_state","automated_posts",
                          "post_journal_state","post_journal_candidates",
                          "account_bundles_state","account_zip_candidates",
                          "account_zip_read_verified","account_registry_state",
                          "account_registry_count"):
                value=snapshot.get(field)
                if isinstance(value,(str,int)) or value is None:
                    print("INTERSECTION_ARCHIVE_AUDIT",field,value,flush=True)
            if snapshot.get("account_zip_candidates",0)>0:
                # This GET reads one latest ZIP from remote storage and checks
                # the immutable name digest AND every manifest object digest.
                # No account identity, source text or cloud credential is logged.
                try:
                    proof=request_json(GATEWAY+"/api/bridge/verify-one",
                                       headers=bridge_headers,timeout=95)
                    state=proof.get("state")
                    if state in ("SHA_VERIFIED","READBACK_TIMED_OUT",
                                 "READBACK_UNVERIFIED","NO_ZIP_CANDIDATES"):
                        print("INTERSECTION_ACCOUNT_ZIP_PROOF",state,
                              "posts",proof.get("posts") if state=="SHA_VERIFIED" else None,
                              "objects",proof.get("objects") if state=="SHA_VERIFIED" else None,
                              flush=True)
                except Exception:
                    print("INTERSECTION_ACCOUNT_ZIP_PROOF_UNAVAILABLE",flush=True)
        except Exception:
            print("INTERSECTION_ARCHIVE_AUDIT_UNAVAILABLE",flush=True)
    pending=request_json(GATEWAY+"/api/bridge/pending",headers=bridge_headers)
    jobs=pending.get("requests",[])
    if not isinstance(jobs,list) or len(jobs)>4:
        raise RuntimeError("Unexpected private queue response")
    if not jobs:
        return "NO_PENDING"
    seen=set()
    dispatched=0
    for task in jobs:
        if not isinstance(task,dict) or set(task)!={"job_id","platform","account"}:
            raise RuntimeError("Invalid private queue selection")
        if (type(task["job_id"]) is not int or
                task["platform"] not in ("bluesky","mastodon") or
                task["job_id"] in seen):
            raise RuntimeError("Invalid selected account backup")
        seen.add(task["job_id"])
        if not isinstance(task["account"],str) or not 3<=len(task["account"])<=260:
            raise RuntimeError("Invalid account input")
        # Every request gets a distinct run, acceptance marker and signed receipt.
        # A slow first workflow does not block later dispatches from this poll.
        github_token=os.environ["GITHUB_TOKEN"]
        dispatch=Request(
            GITHUB+"/actions/workflows/intersection-target-account-bundle.yml/dispatches",
            method="POST",
            data=json.dumps({"ref":"main","return_run_details":True,
                 "inputs":{"platform":task["platform"],"account":task["account"],
                           "max_pages":"all"}}).encode(),
            headers={"Authorization":"Bearer "+github_token,
                     "Accept":"application/vnd.github+json",
                     "Content-Type":"application/json",
                     "X-GitHub-Api-Version":"2026-03-10",
                     "User-Agent":"intersection-account-queue"})
        with urlopen(dispatch,timeout=30) as resp:
            if resp.status!=200:
                raise RuntimeError("Exact GitHub workflow run ID unavailable")
            result=json.load(resp)
        run_id=result.get("workflow_run_id")
        if type(run_id) is not int or run_id<=0:
            raise RuntimeError("Queued run has no trackable GitHub execution")
        ack=request_json(GATEWAY+"/api/bridge/ack",
            headers={**bridge_headers,"Content-Type":"application/json"},
            payload={"job_id":task["job_id"],"workflow_run_id":run_id})
        if ack.get("accepted") is not True or ack.get("job_id")!=task["job_id"]:
            raise RuntimeError("Immutable queue acknowledgment failed")
        dispatched+=1
    print("INTERSECTION_BACKUP_BRIDGE_DISPATCHED_COUNT",dispatched,flush=True)
    return "DISPATCHED"


if __name__=="__main__":
    result=poll_once()
    print("INTERSECTION_DURABLE_BACKUP_"+result)
