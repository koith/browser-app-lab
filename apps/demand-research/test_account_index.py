"""Private account index: 20k synthetic profiles, dedup, deletion, auth and pagination."""
from __future__ import annotations
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
import account_index
import gateway


def post(i, handle=None, original=False):
    handle=handle or ("qa_" + str(i))
    url="https://x.com/"+handle
    result={"id":"synthetic-"+str(i),"platform":"x","posted":"2026-11-02T00:00:00Z",
            "text":"DO_NOT_STORE_PRIVATE_TEXT_" + str(i)}
    if original:
        result["source_url"]=url+"/status/"+str(1000000000000000000+i)
    else:
        result["profile_url"]=url
    return result


def test_strict_account_normalization_and_original_permalink():
    assert account_index.profile_url("https://twitter.com/QA_User")==("x","https://x.com/qa_user")
    assert account_index.profile_url("https://instagram.com/p/")==None
    assert account_index.profile_url("https://x.com.evil.invalid/qa")==None
    assert account_index.profile_url("http://x.com/qa")==None
    assert account_index.profile_url("https://x.com/qa?admin=true")==None
    assert account_index.profile_url("https://bsky.app/profile/demo.bsky.social")==(
        "bluesky","https://bsky.app/profile/demo.bsky.social")
    assert account_index.account_from_post(post(5,original=True))[0]=="https://x.com/qa_5"
    assert account_index.account_from_post({"id":"aaa","platform":"instagram",
              "source_url":"https://instagram.com/p/unknown"}) is None
    assert account_index.account_from_post({"id":"123","platform":"x","profile_url":"https://x.com/safe",
              "restricted":True}) is None


def test_bulk_index_20k_is_paged_and_deduped(tmp_path):
    db=str(tmp_path/"private"/"accounts.sqlite3")
    rows=[post(i) for i in range(20000)]
    result=account_index.sync_catalog(db,rows)
    assert result=={"accepted":20000,"skipped":0}
    assert account_index.status(db)["accounts"]==20000
    assert account_index.page(db,0,80)["total"]==20000
    assert len(account_index.page(db,0,80)["items"])==80
    assert len(account_index.page(db,19980,80)["items"])==20
    assert account_index.page(db,0,80,platform="reddit")["total"]==0
    assert account_index.page(db,0,80,q="qa_19999")["total"]==1
    # Stable catalog re-ingestion must never double count.
    account_index.sync_catalog(db,rows)
    assert account_index.status(db)["source_rows"]==20000
    # A deleted or withdrawn catalog entry must disappear.
    account_index.sync_catalog(db,rows[:19999])
    assert account_index.status(db)["accounts"]==19999
    with sqlite3.connect(db) as conn:
        raw=" ".join(str(x) for x in conn.iterdump())
        assert "DO_NOT_STORE_PRIVATE_TEXT_" not in raw


def test_provider_ingest_and_dedup(tmp_path):
    db=str(tmp_path/"private.sqlite3")
    account_index.sync_catalog(db,[post(1)])
    account_index.ingest_discovery(db,[post(1),post(2)])
    assert account_index.status(db)["accounts"]==2
    # The same source post in two adapters may share account but counts once.
    a=account_index.page(db,0,80)
    assert a["total"]==2
    assert sum(x["verified_posts"] for x in a["items"])==2
    account_index.sync_catalog(db,[])
    assert account_index.status(db)["accounts"]==2


def test_gateway_account_api_requires_signed_session(tmp_path,monkeypatch):
    path=str(tmp_path/"private.sqlite3")
    monkeypatch.setattr(gateway,"INDEX_DB",path)
    monkeypatch.setattr(gateway,"TOKEN","a"*40)
    monkeypatch.setattr(gateway,"COOKIE","permitted-rclone-cookie")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    account_index.sync_catalog(path,[post(1),post(2)])
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.get("/api/accounts/status").status_code==401
    assert client.get("/api/accounts").status_code==401
    assert client.post("/api/accounts/sync").status_code==401
    activate=client.post("/api/activate",json={"token":"a"*40})
    assert activate.status_code==200
    assert client.get("/api/accounts").json()["total"]==2
    assert client.get("/api/accounts/status").json()["accounts"]==2
    assert client.get("/api/accounts?platform=invalid").status_code==400
    assert client.get("/api/accounts?limit=101").status_code==422
    assert client.get("/account_index.py").status_code==404
    assert client.get("/account_index_client.js").status_code==200
    assert client.get("/account_auto_analysis.js").status_code==200
    assert client.post("/api/end-session").status_code==200
    assert client.get("/api/accounts").status_code==401


def test_gateway_missing_account_db_fails_closed(monkeypatch):
    monkeypatch.setattr(gateway,"INDEX_DB","")
    assert TestClient(gateway.app).get("/api/accounts").status_code in (401,503)
