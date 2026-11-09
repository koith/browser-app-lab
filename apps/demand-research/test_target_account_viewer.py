"""Private SNS-like account archive browser contract, all synthetic and offline."""
import json
from fastapi.testclient import TestClient
import pytest

import gateway
import target_account_viewer as viewer
import target_account_enrichment as enrich
from target_account_archive import archive_key,account_cloud
from demand_archive import canonical_json,post_key,sha256,MIMES
from test_demand_archive import FakeCloud

DID="did:plc:"+"a"*24
PROFILE={"platform":"bluesky","identity":DID,
         "actor":DID,"pds":"https://pds.example",
         "profile_url":"https://bsky.app/profile/"+DID}
PID=post_key("bluesky","at://"+DID+"/app.bsky.feed.post/test100")
PHOTO=b"\xff\xd8synthetic-original-photo"
BANNER=b"\x89PNG\r\n\x1a\nsynthetic-public-header"
GRAPH_PERSON={"id":"did:plc:"+"b"*24,"handle":"reader.bsky.social",
              "display_name":"Public Reader",
              "profile_url":"https://bsky.app/profile/did:plc:"+"b"*24}


@pytest.fixture
def populated(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-private-cookie")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    root=FakeCloud()
    name="bluesky-"+archive_key(PROFILE)
    root.write_immutable("metadata/target-accounts/"+name+".json",
                         canonical_json(PROFILE))
    archive=account_cloud(root,PROFILE)
    akey="profile/assets/"+sha256(PHOTO)+".jpg"
    bkey="profile/assets/"+sha256(BANNER)+".png"
    archive.write_immutable(akey,PHOTO)
    archive.write_immutable(bkey,BANNER)
    enrich.save_snapshot(archive,"profile/snapshots",{
        "platform":"bluesky","identity":DID,"handle":"qa-user.bsky.social",
        "display_name":"Public QA","description":"Public biography sample",
        "followers_count":5,"following_count":3,"posts_count":10,
        "captured_at":"2026-11-04T00:00:00Z",
        "complete_media":True,
        "assets":{
            "avatar":{"status":"sha256_verified","key":akey,"mime":"image/jpeg",
                      "sha256":sha256(PHOTO),"bytes":len(PHOTO)},
            "banner":{"status":"sha256_verified","key":bkey,"mime":"image/png",
                      "sha256":sha256(BANNER),"bytes":len(BANNER)}}})
    archive.write_immutable("graph/pages/followers-00000001.json",
                             canonical_json({"items":[GRAPH_PERSON],"kind":"followers",
                                             "source_count":1,"next_cursor":None}))
    archive.write_immutable("graph/pages/following-00000001.json",
                             canonical_json({"items":[GRAPH_PERSON],"kind":"following",
                                             "source_count":1,"next_cursor":None}))
    post={"id":PID,"platform":"bluesky",
          "original_id":"at://"+DID+"/app.bsky.feed.post/test100",
          "text":"This is a saved public post",
          "source_url":"https://bsky.app/profile/"+DID+"/post/test100",
          "posted_at":"2026-11-03T00:00:00Z",
          "kind":"post","reply_to":"",
          "media":[{"key":"posts/"+PID+"/media/0001.jpg",
                    "bytes":len(PHOTO),"sha256":sha256(PHOTO),"mime":"image/jpeg",
                    "remote_verified":True,"kind":"image"}],
          "media_saved":1,"media_expected":1,"archive_complete":True}
    archive.save_post(post,[PHOTO])
    enrich.save_snapshot(archive,"threads/"+PID,{
        "post_id":PID,"source_url":post["source_url"],
        "captured_at":"2026-11-04T00:00:00Z",
        "replies":[{"id":"reply001","author":"reader.bsky.social",
                    "display_name":"Public Reader",
                    "text":"Public comment archived",
                    "posted_at":"2026-11-03T01:00:00Z",
                    "uri":"https://bsky.app/profile/reader.bsky.social/post/123",
                    "media_urls":[]}],
        "truncated":False})
    monkeypatch.setattr(viewer,"open_root",lambda:root)
    monkeypatch.setattr(gateway,"TOKEN","synthetic-viewer-private-link-token-0123456789")
    monkeypatch.setattr(gateway,"COOKIE","synthetic-private-cookie")
    client=TestClient(gateway.app,base_url="https://testserver")
    assert client.post("/api/activate",json={
        "token":"synthetic-viewer-private-link-token-0123456789"}).status_code==200
    return client,root,archive,name


def test_private_archive_enforces_session(populated):
    _client,root,archive,name=populated
    no=TestClient(gateway.app,base_url="https://testserver")
    for path in ("/account-archive",
                 "/account-archive/account_archive_view.js",
                 "/api/account-archives",
                 "/api/account-archives/"+name+"/feed",
                 "/api/account-archives/"+name+"/profile"):
        assert no.get(path).status_code==401,path


def test_private_viewer_html_and_static_assets_no_secrets(populated):
    client,*_=populated
    html=client.get("/account-archive")
    assert html.status_code==200
    assert "계정 보관함" in html.text
    assert "script-src 'self'" in html.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in html.headers["content-security-policy"]
    assert "frame-ancestors 'none'" not in html.headers["content-security-policy"]
    assert "no-store" in html.headers["cache-control"]
    js=client.get("/account-archive/account_archive_view.js")
    css=client.get("/account-archive/account_archive_view.css")
    assert js.status_code==200 and css.status_code==200
    assert "textContent" in js.text
    assert client.get("/account-archive/gateway.py").status_code==404
    assert "synthetic-private-cookie" not in html.text+js.text+css.text


def test_private_account_profile_bio_header_and_original_photo(populated):
    client,root,archive,name=populated
    accounts=client.get("/api/account-archives")
    assert accounts.status_code==200
    assert accounts.json()["accounts"][0]["key"]==name
    assert accounts.json()["accounts"][0]["display_name"]=="Public QA"
    assert accounts.json()["accounts"][0]["handle"]=="qa-user.bsky.social"
    assert accounts.json()["accounts"][0]["profile_snapshot_verified"] is True
    profile=client.get("/api/account-archives/"+name+"/profile")
    assert profile.status_code==200
    p=profile.json()
    assert p["description"]=="Public biography sample"
    assert p["handle"]=="qa-user.bsky.social"
    assert p["followers_count"]==5
    assert p["following_count"]==3
    assert p["assets"]["avatar"].endswith("/avatar")
    assert p["assets"]["banner"].endswith("/banner")
    assert client.get(p["assets"]["avatar"]).content==PHOTO
    assert client.get(p["assets"]["banner"]).content==BANNER


def test_source_verified_feed_exact_original_range_and_comment_thread(populated):
    client,root,archive,name=populated
    feed=client.get("/api/account-archives/"+name+"/feed?limit=20")
    assert feed.status_code==200
    data=feed.json()
    assert data["total"]==1 and len(data["posts"])==1
    p=data["posts"][0]
    assert p["kind"]=="post"
    assert p["text"]=="This is a saved public post"
    assert p["media"][0]["verified_sha256"] is True
    url=p["media"][0]["url"]
    full=client.get(url)
    assert full.status_code==200 and full.content==PHOTO
    half=client.get(url,headers={"Range":"bytes=0-4"})
    assert half.status_code==206 and half.content==PHOTO[:5]
    thread=client.get("/api/account-archives/"+name+"/threads/"+PID)
    assert thread.status_code==200
    assert thread.json()["replies"][0]["text"]=="Public comment archived"
    assert thread.json()["comment_media_backed_up"] is False


def test_public_followers_and_follows_are_paged_archive_only(populated):
    client,root,archive,name=populated
    for kind in ("followers","following"):
        first=client.get("/api/account-archives/"+name+"/graph/"+kind)
        assert first.status_code==200
        response=first.json()
        assert response["captured_unique"]==1
        assert response["full_network_coverage_guaranteed"] is False
        assert response["accounts"][0]["handle"]=="reader.bsky.social"
        assert client.get("/api/account-archives/"+name+"/graph/"+kind+
                          "?offset=1").json()["accounts"]==[]


def test_wrong_account_or_integrity_corruption_never_serves_media(populated):
    client,root,archive,name=populated
    url="/api/account-archives/"+name+"/media/"+PID+"/0"
    archive_path="account-archives/bluesky/"+archive_key(PROFILE)+"/posts/"+PID+"/media/0001.jpg"
    root.objects[archive_path]=b"wrong picture bytes"
    assert client.get(url).status_code==502
    assert client.get("/api/account-archives/bluesky-"+"b"*40+"/feed").status_code==404
    assert client.get("/api/account-archives/"+name+"/media/"+"z"*40+"/0").status_code==400
    assert client.get("/api/account-archives/"+name+"/profile-asset/nonexistent").status_code==400
    assert client.get("/api/account-archives/"+name+"/graph/notallowed").status_code==400


def test_browser_source_prevents_raw_html_execution(populated):
    client,*_=populated
    script=client.get("/account-archive/account_archive_view.js").text
    assert ".textContent=" in script
    assert "innerHTML=" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "document.cookie" not in script



def test_verified_bundle_choice_uses_archived_nickname_not_url(populated,monkeypatch):
    from types import SimpleNamespace
    client,root,archive,name=populated
    prefix="account-archives/bluesky/"+archive_key(PROFILE)+"/"
    snapshot={
        "platform":"bluesky","identity":DID,
        "handle":"qa-user.bsky.social","display_name":"Public QA"}
    key=prefix+"profile/snapshots/snap-"+"0"*20+"-"+"a"*16+".json"
    bundle=SimpleNamespace(
        account=name,accounts={name:PROFILE},selected_platform="bluesky",
        selected_account=DID,prefix=prefix,
        items={key:canonical_json(snapshot)},post_count=6,
        object_count=12,source_state="sha256_verified",temporary=True)
    row=viewer.bundled_account_picker_row(bundle,name,temporary=True)
    assert row["display_name"]=="Public QA"
    assert row["handle"]=="qa-user.bsky.social"
    assert row["profile_snapshot_verified"] is True
    assert row["posts_verified_in_bundle"]==6
    assert row["profile_url"]==PROFILE["profile_url"]

    monkeypatch.setattr("github_temp_bundle.enabled",lambda:True)
    monkeypatch.setattr("github_temp_bundle.latest_bundles",lambda:iter([bundle]))
    monkeypatch.setattr(viewer,"_verified_account_bundles",lambda root:iter(()))
    response=client.get("/api/account-archives")
    assert response.status_code==200
    assert response.json()["accounts"][0]["display_name"]=="Public QA"
    assert response.json()["accounts"][0]["handle"]=="qa-user.bsky.social"


def test_unmatched_snapshot_never_injects_another_account_name(populated):
    _client,root,archive,name=populated
    class WrongIdentity:
        def names(self,prefix):
            return ["snap-"+"0"*20+"-"+"b"*16+".json"]
        def read(self,key,*,cap=300000,optional=True):
            return json.dumps({"platform":"bluesky","identity":"did:plc:"+"b"*24,
                               "display_name":"Another Account",
                               "handle":"other.bsky.social"}).encode()
    result=viewer.account_picker_details(PROFILE,WrongIdentity())
    assert result["profile_snapshot_verified"] is False
    assert result["display_name"]==""
    assert result["handle"]==""
