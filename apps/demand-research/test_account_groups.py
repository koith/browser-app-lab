"""A single self-declared cross-SNS operator with 10 accounts is shown as one
connection group. Other people's accounts must NEVER be silently merged.
"""
from __future__ import annotations
import time
import pytest
from fastapi.testclient import TestClient
import account_index, account_groups, gateway


def corpus():
    profiles = (
        [("bluesky","https://bsky.app/profile/qa%d.bsky.social" % i) for i in range(4)] +
        [("mastodon","https://mastodon.social/@qa%d" % i) for i in range(3)] +
        [("x","https://x.com/qagroup%d" % i) for i in range(3)]
    )
    return profiles


def post(i, platform, url):
    return {"id":"public-example-%d"%i,"platform":platform,
            "profile_url":url,"posted":"2026-11-02T00:00:00Z"}


def test_explicit_link_extraction_and_promotion_exclusion():
    assert account_groups.declared_accounts(
        "My other account https://bsky.app/profile/qa.bsky.social"
    ) == ["https://bsky.app/profile/qa.bsky.social"]
    assert account_groups.declared_accounts(
        "Follow my friend https://bsky.app/profile/qa.bsky.social"
    ) == []
    assert account_groups.declared_accounts(
        "내 다른 계정 https://mastodon.social/@qa"
    ) == ["https://mastodon.social/@qa"]
    assert account_groups.declared_accounts(
        "My other account https://bsky.app.evil.invalid/profile/qa"
    ) == []
    assert account_groups.declared_accounts(
        "My other account https://bsky.app/profile/qa.bsky.social?token=a"
    ) == []


def test_one_A_group_contains_ten_accounts_and_excludes_promotional_link(tmp_path):
    db=str(tmp_path/"private.sqlite3")
    accounts=corpus()
    extra=("x","https://x.com/otherfriend")
    rows=[post(i,*t) for i,t in enumerate(accounts+[extra])]
    account_index.sync_catalog(db,rows)
    assert account_index.status(db)["accounts"]==11
    first=accounts[0][1];now=int(time.time())
    # Centre account and all its 9 aliases explicitly self-declare each other.
    account_groups.replace_claims(db,first,[u for _,u in accounts[1:]],when=now)
    for _,u in accounts[1:]:
        account_groups.replace_claims(db,u,[first],when=now)
    # Friend says "my other account" but central account does not reciprocate.
    account_groups.replace_claims(db,extra[1],[first],when=now)
    result=account_groups.groups_page(db,now=now)
    assert result["total"]==1
    assert result["account_count"]==11
    assert result["linked_accounts"]==10
    assert result["unresolved_accounts"]==1
    assert result["deduplicated_account_units"]==2
    assert result["distinct_people_verified"] is False
    group=result["items"][0]
    assert group["group_id"].startswith("A-")
    assert group["account_count"]==10
    assert group["distinct_posts"]==10
    assert len(group["accounts"])==10
    assert all(c["profileUrl"]!=extra[1] for c in group["accounts"])
    # Identical observations from two ingestion channels never count twice.
    account_index.ingest_discovery(db,[post(0,*accounts[0])])
    assert account_groups.groups_page(db,now=now)["items"][0]["distinct_posts"]==10
    # Withdrawn/expired proofs stop merging.
    assert account_groups.groups_page(db,now=now+account_groups.EVIDENCE_TTL+1)["total"]==0
    account_groups.replace_claims(db,accounts[1][1],[],when=now)
    assert account_groups.groups_page(db,now=now)["items"][0]["account_count"]==9


def test_rotating_bounded_official_profile_scan(tmp_path):
    db=str(tmp_path/"private.sqlite3")
    accounts=corpus()[:4]
    account_index.sync_catalog(db,[post(i,*entry) for i,entry in enumerate(accounts)])
    scanned=[]
    def remote(actors):
        scanned.extend(actors)
        return [{"handle":a,"description":"My other account https://bsky.app/profile/qa1.bsky.social"}
                for a in actors]
    result=account_groups.scan_known_profiles(db,max_profiles=2,bsky_fetch=remote)
    assert result["checked"]==2 and result["failed"]==0
    assert len(scanned)==2
    account_groups.scan_known_profiles(db,max_profiles=2,bsky_fetch=remote)
    assert len(set(scanned))==4


def test_gateway_group_endpoint_requires_auth_and_is_paginated(tmp_path,monkeypatch):
    db=str(tmp_path/"private.sqlite3")
    accounts=corpus()
    account_index.sync_catalog(db,[post(i,*entry) for i,entry in enumerate(accounts)])
    a,b=accounts[:2];now=int(time.time())
    account_groups.replace_claims(db,a[1],[b[1]],when=now)
    account_groups.replace_claims(db,b[1],[a[1]],when=now)
    monkeypatch.setattr(gateway,"INDEX_DB",db)
    monkeypatch.setattr(gateway,"TOKEN","s"*40)
    monkeypatch.setattr(gateway,"COOKIE","private-test-cloud")
    monkeypatch.setattr(gateway,"REMOTE","archive:DemandResearch")
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.get("/api/account-groups").status_code==401
    assert client.post("/api/activate",json={"token":"s"*40}).status_code==200
    data=client.get("/api/account-groups?limit=1").json()
    assert data["total"]==1 and len(data["items"])==1
    assert data["items"][0]["account_count"]==2
    assert client.get("/api/account-groups?limit=101").status_code==422
    assert client.get("/account_group_client.js").status_code==200
    assert client.get("/account_groups.py").status_code==404
