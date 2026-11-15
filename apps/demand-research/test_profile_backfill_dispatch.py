"""Offline verification of signed, deduplicated archive index handoff."""
from __future__ import annotations
import io
import json
from types import SimpleNamespace
import profile_backfill_dispatch as repair

ACCOUNT="bluesky-"+"a"*40
TAG="intersection-github-archive-43687951260-a1"
DID="did:plc:"+"a"*24


def test_verified_private_zip_inventory_has_exact_signed_owner(monkeypatch):
    profile={"platform":"bluesky","identity":DID,
             "profile_url":"https://bsky.app/profile/"+DID}
    blob=SimpleNamespace(
        account=ACCOUNT,archive_tag=TAG,accounts={ACCOUNT:profile},
        post_count=6,object_count=44,recorded_at="2026-11-15T00:00:00Z")
    class Reader:
        def __init__(self,*_):pass
        def names(self,_):return ["snap-"+"1"*20+"-"+"b"*16+".json"]
        def read(self,*_,**__):return json.dumps({
            "platform":"bluesky","identity":DID,"display_name":"Stored QA",
            "handle":"qa.bsky.social"}).encode()
    monkeypatch.setattr(repair,"BundleAccountCloud",Reader)
    items=repair.saved_accounts([blob,blob])
    assert len(items)==1 and items[0]["platform"]=="bluesky"
    row=items[0]["index_row"]
    assert row["release_tag"]==TAG
    assert row["account_key"]==ACCOUNT
    assert row["workflow_run_id"]==43687951260
    assert row["posts_verified"]==6 and row["objects_verified"]==44
    assert row["display_name"]=="Stored QA"


def test_index_only_uses_signed_bridge_and_dispatches_no_capture(monkeypatch):
    row={"platform":"bluesky","account":"https://bsky.app/profile/"+DID,
         "index_row":{"account_key":ACCOUNT,"platform":"bluesky",
                      "release_tag":TAG,"workflow_run_id":43687951260,
                      "profile_url":"https://bsky.app/profile/"+DID,
                      "display_name":"","handle":"qa.bsky.social",
                      "recorded_at":"","posts_verified":6,"objects_verified":44}}
    monkeypatch.setenv("GITHUB_REPOSITORY","koith/browser-app-lab")
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_TOKEN","synthetic-actions-token-only")
    monkeypatch.setenv("PROFILE_INDEX_ONLY","true")
    monkeypatch.setattr(repair.github_temp_bundle,"workflow_verified_bundles",
                        lambda max_scan:iter(["synthetic-verified"]))
    monkeypatch.setattr(repair,"saved_accounts",lambda _: [row])
    calls={"indexed":0,"dispatched":0}
    def import_index(items):
        assert len(items)==1
        calls["indexed"]+=1
    monkeypatch.setattr(repair,"import_durable_index",import_index)
    monkeypatch.setattr(repair,"dispatch_one",
                        lambda *_:calls.__setitem__("dispatched",calls["dispatched"]+1))
    repair.main()
    assert calls=={"indexed":1,"dispatched":0}


def test_signed_index_transport_never_sends_token_in_url(monkeypatch):
    import os
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL","https://github.example/oidc?foo=1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN","synthetic-workflow-runtime-secret")
    requests=[]
    class Response:
        status=200
        def __init__(self,body):self.body=json.dumps(body).encode()
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def read(self,_=None):return self.body
    def fetch(request,timeout=20):
        requests.append(request)
        if len(requests)==1:return Response({"value":"a"*180})
        return Response({"accepted":True,"stored":1})
    monkeypatch.setattr(repair,"urlopen",fetch)
    repair.import_durable_index([{"index_row":{"account_key":ACCOUNT}}])
    assert len(requests)==2
    assert "synthetic-workflow-runtime-secret" not in requests[0].full_url
    assert "/api/bridge/archive-index" in requests[1].full_url
    assert requests[1].get_header("Authorization")=="Bearer "+"a"*180
    assert requests[1].data is not None
