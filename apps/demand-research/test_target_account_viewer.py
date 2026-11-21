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
    assert accounts.json()["accounts"][0]["profile_snapshot_verified"] is False
    profile=client.get("/api/account-archives/"+name+"/profile")
    assert profile.status_code==200
    p=profile.json()
    assert p["description"]=="Public biography sample"
    assert p["handle"]=="qa-user.bsky.social"
    assert p["followers_count"]==5
    assert p["following_count"]==3
    assert "/profile-asset/avatar?snapshot=" in p["assets"]["avatar"]
    assert "/profile-asset/banner?snapshot=" in p["assets"]["banner"]
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


def test_entire_verified_feed_search_kind_media_and_missing_slots(populated):
    """Independent subtask gates: global text search, type filter, completeness
    filter and exact source attachment indices, no other-original substitution."""
    client,_,_,name=populated
    a="a"*40
    b="b"*40
    d="d"*40
    rows=[
      {"id":a,"text":"서울 아침 커피","kind":"post",
       "media_expected":0,"media_saved":0,"archive_complete":True,"media":[]},
      {"id":b,"text":"서울 밤 산책","kind":"reply",
       "media_expected":3,"media_saved":1,"archive_complete":False,
       "media":[{"key":"posts/"+b+"/media/0001.png",
                 "remote_verified":True,"mime":"image/png","bytes":10,"kind":"image"},
                {"key":"posts/"+b+"/media/0002.png",
                 "remote_verified":False,"mime":"image/png","bytes":20,"kind":"image"}]},
      {"id":d,"text":"서울 새벽 기록 수정","kind":"post","revision_of":a,
       "media_expected":0,"media_saved":0,"archive_complete":True,"media":[]},
    ]
    class Journal:
        def load_catalog(self,include_entries=False):
            assert include_entries
            return rows
    full=viewer.feed_data(Journal(),name,0,2,q="서울")
    assert full["total"]==3 and len(full["posts"])==2 and full["more"] is True
    last=viewer.feed_data(Journal(),name,2,2,q="서울")
    assert last["total"]==3 and last["posts"][0]["id"]==d
    assert viewer.feed_data(Journal(),name,0,20,q="밤")["posts"][0]["id"]==b
    assert viewer.feed_data(Journal(),name,0,20,q="없는 글")["total"]==0
    assert viewer.feed_data(Journal(),name,0,20,kind="reply")["posts"][0]["id"]==b
    assert viewer.feed_data(Journal(),name,0,20,kind="revision")["posts"][0]["id"]==d
    assert viewer.feed_data(Journal(),name,0,20,kind="post")["posts"][0]["id"]==a
    # SNS media tab must show real saved attachment positions, never a
    # text-only post as a fabricated media item.
    media_only=viewer.feed_data(Journal(),name,0,20,media_status="has_media")
    assert media_only["total"]==1 and media_only["posts"][0]["id"]==b
    assert viewer.feed_data(Journal(),name,0,20,kind="post",
                            media_status="has_media")["total"]==0
    partial=viewer.feed_data(Journal(),name,0,20,media_status="partial")
    assert partial["total"]==1 and partial["posts"][0]["id"]==b
    media=partial["posts"][0]["media"]
    assert [x["index"] for x in media]==[0,1]
    assert media[0]["verified_sha256"] and media[0]["url"].endswith("/0")
    assert media[1]["verified_sha256"] is False and media[1]["url"] is None
    assert viewer.feed_data(Journal(),name,0,20,media_status="complete")["total"]==2
    # Authentication and validated private API contract use the same filters.
    assert client.get("/api/account-archives/"+name+"/feed?q=saved").json()["total"]==1
    assert client.get("/api/account-archives/"+name+"/feed?kind=reply").json()["total"]==0
    assert client.get("/api/account-archives/"+name+"/feed?media_status=complete").json()["total"]==1
    assert client.get("/api/account-archives/"+name+"/feed?kind=invalid").status_code==400
    assert client.get("/api/account-archives/"+name+"/feed?media_status=invalid").status_code==400
    assert client.get("/api/account-archives/"+name+"/feed?q="+("x"*101)).status_code==422


def test_verified_incremental_history_status_includes_older_originals(populated,monkeypatch):
    """A newest empty incremental ZIP is NOT an empty archived account."""
    from types import SimpleNamespace
    client,_,_,account=populated
    prefix="account-archives/bluesky/"+archive_key(PROFILE)+"/"
    older=SimpleNamespace(
        account=account,prefix=prefix,recorded_at="2026-11-01T00:00:00Z",
        post_count=1,object_count=3,source_state="RESUME_NEEDED",temporary=True,
        items={prefix+"posts/"+PID+"/post.json":b"original-entry",
               prefix+"profile/snapshots/first.json":b"first",
               "metadata/target-accounts/"+account+".json":b"identity"})
    latest=SimpleNamespace(
        account=account,prefix=prefix,recorded_at="2026-11-12T00:00:00Z",
        post_count=0,object_count=2,
        source_state="COMPLETE_CURRENT_PUBLIC_CURSOR",temporary=True,
        items={prefix+"profile/snapshots/latest.json":b"latest",
               "metadata/target-accounts/"+account+".json":b"identity"})
    archive=viewer.MergedBundleAccountCloud([latest,older])
    monkeypatch.setattr(viewer,"open_account",
                        lambda _account:(None,PROFILE,archive))
    status=client.get("/api/account-archives/"+account+"/backup-status")
    assert status.status_code==200
    body=status.json()
    assert body["storage"]=="github_encrypted_temporary"
    assert body["state"]=="REMOTE_ZIP_SHA_VERIFIED"
    assert body["verified_history_zips"]==2
    assert body["latest_zip_public_posts"]==0
    assert body["public_posts"]==1
    assert body["original_objects"]==4
    assert body["full_historical_coverage_guaranteed"] is False


def test_render_verified_bundle_singleflight_never_redecrypts_8_parallel_reads(monkeypatch):
    """No duplicate big ZIP in eight concurrent real-gateway endpoints."""
    from concurrent.futures import ThreadPoolExecutor
    import threading,time
    monkeypatch.setenv("DEMAND_ACCOUNT_VIEWER_SESSION_CACHE","1")
    monkeypatch.setattr(viewer,"_ARCHIVE_SESSION_CACHE",None)
    calls=[]
    lock=threading.Lock()
    def verified_archive(account):
        with lock:calls.append(account)
        time.sleep(.025)
        return (None,{"platform":"bluesky","identity":"synthetic"},object())
    monkeypatch.setattr(viewer,"_open_account_uncached",verified_archive)
    acc="bluesky-"+"a"*40
    with ThreadPoolExecutor(max_workers=8) as pool:
        values=list(pool.map(viewer.open_account,[acc]*8))
    assert len(calls)==1 and all(value is values[0] for value in values)
    other="mastodon-"+"b"*40
    assert viewer.open_account(other) is not values[0]
    assert calls==[acc,other]
    old=viewer._ARCHIVE_SESSION_CACHE
    monkeypatch.setattr(viewer,"_ARCHIVE_SESSION_CACHE",
                        (old[0],time.monotonic()-viewer.ARCHIVE_SESSION_SECONDS-1,old[2]))
    assert viewer.open_account(other) is not old[2]
    assert len(calls)==3


def test_render_verified_bundle_cache_never_caches_errors_or_another_account(
        monkeypatch):
    monkeypatch.setenv("DEMAND_ACCOUNT_VIEWER_SESSION_CACHE","1")
    monkeypatch.setattr(viewer,"_ARCHIVE_SESSION_CACHE",None)
    calls=[]
    def _open(account):
        calls.append(account)
        if len(calls)==1:raise RuntimeError("synthetic SHA mismatch")
        return (None,{"platform":"bluesky","identity":"synthetic"},object())
    monkeypatch.setattr(viewer,"_open_account_uncached",_open)
    account="bluesky-"+"c"*40
    with pytest.raises(RuntimeError,match="SHA mismatch"):
        viewer.open_account(account)
    assert viewer._ARCHIVE_SESSION_CACHE is None
    verified=viewer.open_account(account)
    assert viewer.open_account(account) is verified
    assert len(calls)==2
    monkeypatch.delenv("DEMAND_ACCOUNT_VIEWER_SESSION_CACHE",raising=False)
    assert viewer.open_account(account) is not verified
    assert len(calls)==3


def test_expired_free_worker_history_is_evicted_before_sha_loading_next(
        monkeypatch):
    """Cannot retain two complete 200MiB immutable ZIP unions in 512MiB."""
    import time
    monkeypatch.setenv("DEMAND_ACCOUNT_VIEWER_SESSION_CACHE","1")
    now=time.monotonic()
    monkeypatch.setattr(viewer,"_ARCHIVE_SESSION_CACHE",(
        "bluesky-"+"a"*40,now-viewer.ARCHIVE_SESSION_SECONDS-2,
        (None,{"platform":"bluesky"},object())))
    observations=[]
    def cold_open(account):
        observations.append(viewer._ARCHIVE_SESSION_CACHE is None)
        return (None,{"platform":"bluesky"},object())
    monkeypatch.setattr(viewer,"_open_account_uncached",cold_open)
    newer=viewer.open_account("bluesky-"+"b"*40)
    assert observations==[True]
    assert viewer.open_account("bluesky-"+"b"*40) is newer
    assert len(observations)==1

def test_github_sha_reader_does_not_repeat_denied_terabox_probe_each_media(
        monkeypatch):
    """Keep verified GitHub access responsive under independent TeraBox 403."""
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    monkeypatch.setattr(viewer,"_ZIP_SESSION_CACHE",None)
    calls=[]
    def denied(_root):
        calls.append(1)
        raise RuntimeError("(authorization) synthetic private provider denied")
    monkeypatch.setattr(viewer,"available_bundles",denied)
    root=viewer.CloudArchive(remote="archive:DemandResearch",
                             runner=lambda *a,**k:None)
    with pytest.raises(RuntimeError):
        viewer._verified_account_bundles(root)
    assert len(calls)==1
    for _ in range(5):
        with pytest.raises(RuntimeError,match="temporarily unavailable"):
            viewer._verified_account_bundles(root)
    assert len(calls)==1,"do not turn each feed/media/profile request into 30s probe"
    assert 120<=viewer.ZIP_UNAVAILABLE_BACKOFF_SECONDS<300
    # No permanent denial: next session can retry the TeraBox source.
    monkeypatch.setattr(
        viewer,"_ZIP_SESSION_CACHE",
        (root.remote,viewer.time.monotonic()-
         viewer.ZIP_UNAVAILABLE_BACKOFF_SECONDS-1,(),True))
    with pytest.raises(RuntimeError):
        viewer._verified_account_bundles(root)
    assert len(calls)==2


def test_parallel_archive_reads_allow_only_one_failed_terabox_probe(
        monkeypatch):
    """Real Render 403 must not repeat across 8 simultaneous media requests."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    monkeypatch.setattr(viewer,"_ZIP_SESSION_CACHE",None)
    attempts=[]
    def once(_root):
        attempts.append(1)
        time.sleep(0.04)
        raise RuntimeError("(authorization) mock provider denied")
    monkeypatch.setattr(viewer,"available_bundles",once)
    def request(_):
        root=viewer.CloudArchive(remote="archive:DemandResearch",
                                 runner=lambda *a,**kw:None)
        try:
            viewer._verified_account_bundles(root)
        except RuntimeError:
            return "blocked"
        return "unexpected_success"
    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes=list(workers.map(request,range(8)))
    assert len(attempts)==1, (
        "all simultaneous verified archive requests must share a single "
        "provider denial instead of starting 8 slow rclone subprocesses")
    assert outcomes==["blocked"]*8
    assert viewer._ZIP_SESSION_CACHE[3] is True


def test_saved_second_original_never_becomes_first_media_slot(populated,monkeypatch):
    """The saved /media/0002 is not allowed to replace missing /media/0001."""
    client,root,archive,account=populated
    pid="c"*40
    record={
        "id":pid,"platform":"bluesky","text":"Archived exact media slot",
        "source_url":"https://bsky.app/profile/qa/post/test2",
        "posted_at":"2026-11-03T00:00:00Z",
        "media_expected":2,"media_saved":1,"archive_complete":False,
        "media":[{"key":"posts/"+pid+"/media/0002.jpg",
                  "mime":"image/jpeg","kind":"image","bytes":len(PHOTO),
                  "sha256":sha256(PHOTO),"remote_verified":True}]}
    class ExactArchive:
        def load_catalog(self,include_entries=False): return [record]
        def read_verified(self,key,digest,*,cap):
            return PHOTO if key==record["media"][0]["key"] and digest==sha256(PHOTO) else None
    monkeypatch.setattr(viewer,"open_account",
                        lambda _: (None,PROFILE,ExactArchive()))
    feed=client.get("/api/account-archives/"+account+"/feed")
    assert feed.status_code==200
    media=feed.json()["posts"][0]["media"]
    assert len(media)==1 and media[0]["index"]==1
    assert media[0]["url"].endswith("/1")
    assert client.get("/api/account-archives/"+account+"/media/"+pid+"/0").status_code==404
    image=client.get("/api/account-archives/"+account+"/media/"+pid+"/1",
                     headers={"Range":"bytes=0-4"})
    assert image.status_code==206 and image.content==PHOTO[:5]


def test_reordered_original_files_never_change_source_slots(populated):
    _,_,_,account=populated
    pid="e"*40
    rows=[{"id":pid,"text":"source slots test","kind":"post",
           "media_expected":3,"media_saved":2,"archive_complete":False,
           "media":[{"key":"posts/"+pid+"/media/0003.jpg",
                      "mime":"image/jpeg","remote_verified":True},
                     {"key":"posts/"+pid+"/media/0001.jpg",
                      "mime":"image/jpeg","remote_verified":True},
                     {"key":"posts/"+"f"*40+"/media/0002.jpg",
                      "mime":"image/jpeg","remote_verified":True}]}]
    class Journal:
        def load_catalog(self,include_entries=False): return rows
    saved=viewer.feed_data(Journal(),account,0,20)["posts"][0]["media"]
    assert [x["index"] for x in saved]==[0,2]
    assert [x["url"].rsplit("/",1)[-1] for x in saved]==["0","2"]
    assert viewer.archived_media_slot(pid,{"key":"posts/other/media/0001.jpg"}) is None
    assert viewer.archived_media_slot(pid,{"key":"posts/"+pid+"/media/0017.jpg"}) is None


def test_saved_biography_and_header_versions_survive_later_unavailable_capture(populated):
    client,root,archive,name=populated
    original=archive.names("profile/snapshots")[-1]
    enrich.save_snapshot(archive,"profile/snapshots",{
        "platform":"bluesky","identity":DID,"handle":"qa-user.bsky.social",
        "display_name":"Updated QA","description":"Updated long public biography",
        "pronouns":"they/them","website":"https://example.com/profile",
        "followers_count":7,"following_count":5,"posts_count":12,
        "captured_at":"2026-11-15T00:00:00Z",
        "assets":{"avatar":{"status":"unavailable"},
                  "banner":{"status":"unavailable"}}})
    latest=client.get("/api/account-archives/"+name+"/profile")
    assert latest.status_code==200
    page=latest.json()
    assert page["description"]=="Updated long public biography"
    assert page["pronouns"]=="they/them"
    assert page["assets"]["banner"].endswith("snapshot="+original)
    assert page["asset_status"]["banner"]["historical_fallback"] is True
    assert page["asset_status"]["avatar"]["historical_fallback"] is True
    assert len(page["history"])==2
    assert client.get(page["assets"]["banner"]).content==BANNER
    earlier=client.get("/api/account-archives/"+name+"/profile?snapshot="+original)
    assert earlier.status_code==200
    assert earlier.json()["description"]=="Public biography sample"
    assert earlier.json()["assets"]["banner"].endswith("snapshot="+original)
    assert client.get("/api/account-archives/"+name+
                      "/profile?snapshot=wrong.json").status_code==400
    assert client.get("/api/account-archives/"+name+
                      "/profile-asset/banner?snapshot=wrong.json").status_code==400
    # A later explicitly removed header MUST NOT be silently resurrected.
    enrich.save_snapshot(archive,"profile/snapshots",{
        "platform":"bluesky","identity":DID,"display_name":"Updated QA",
        "description":"","captured_at":"2026-11-16T00:00:00Z",
        "assets":{"banner":{"status":"not_set"},
                  "avatar":{"status":"not_set"}}})
    removed=client.get("/api/account-archives/"+name+"/profile").json()
    assert removed["description"]==""
    assert removed["assets"]["banner"] is None
    assert len(removed["history"])==3
    # The prior saved artwork and previous biography remain retrievable.
    assert client.get("/api/account-archives/"+name+
                      "/profile?snapshot="+original).json()["description"]=="Public biography sample"


def test_all_owner_verified_accounts_listed_without_recent_atom_limit(populated,monkeypatch):
    client,*_=populated
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","github_release")
    import backup_queue
    rows=[{
       "account_key":"bluesky-"+format(n,"040x"),
       "platform":"bluesky","release_tag":
            "intersection-github-archive-"+str(43687950000+n)+"-a1",
       "workflow_run_id":43687950000+n,
       "profile_url":"https://bsky.app/profile/did:plc:"+"a"*24,
       "display_name":"Verified source "+str(n),
       "handle":"synthetic"+str(n)+".bsky.social",
       "posts_verified":2,"objects_verified":5}
       for n in range(1,15)]
    monkeypatch.setattr(backup_queue,"archive_index_rows",lambda:rows)
    def no_release_download(*_args,**_kwargs):
        raise AssertionError("owner picker re-downloaded encrypted releases")
    monkeypatch.setattr(viewer.github_temp_bundle,"latest_bundles",no_release_download)
    response=client.get("/api/account-archives")
    assert response.status_code==200
    records=response.json()["accounts"]
    assert len(records)==14
    assert len({item["key"] for item in records})==14
    assert all(item["index_requires_original_recheck"] for item in records)


def test_bluesky_immutable_facets_quote_and_alt_render_without_live_provider(populated):
    client,_,archive,name=populated
    uri="at://"+DID+"/app.bsky.feed.post/test100"
    phrase="안녕 😊 안전한 링크"
    start=len("안녕 😊 ".encode("utf-8"))
    end=len(phrase.encode("utf-8"))
    source={"uri":uri,"value":{
        "$type":"app.bsky.feed.post","text":phrase,
        "facets":[{"index":{"byteStart":start,"byteEnd":end},
                   "features":[{"$type":"app.bsky.richtext.facet#link",
                                "uri":"https://example.org/source"}]}],
        "embed":{"$type":"app.bsky.embed.recordWithMedia",
                 "record":{"record":{"uri":"at://"+DID+
                          "/app.bsky.feed.post/quote001"}},
                 "media":{"images":[{"alt":"원본 작성자의 이미지 설명"}]}}}}
    archive.write_immutable("metadata/source-records/"+PID+".json",canonical_json(source))
    post={"id":PID,"platform":"bluesky","original_id":uri,"text":phrase}
    result=viewer._source_ui(archive,post)
    assert "".join(x["text"] for x in result["rich_text"])==phrase
    assert result["rich_text"][-1]["href"]=="https://example.org/source"
    assert result["alt_text"]==["원본 작성자의 이미지 설명"]
    assert result["quoted_post"]["url"].endswith("/post/quote001")
    assert result["sensitive"] is False


def test_saved_mastodon_cw_poll_and_boost_have_verified_safe_text():
    source={"id":"1234","visibility":"public","sensitive":True,
            "spoiler_text":"콘텐츠 주의",
            "content":'<p>첫줄 <a href="https://valid.example/source">연결</a></p>',
            "pinned":True,"media_attachments":[{"description":"텍스트 설명"}],
            "poll":{"expired":True,"options":[{"title":"찬성","votes_count":3},
                                               {"title":"반대","votes_count":2}]},
            "favourites_count":7,"reblogs_count":1,"replies_count":2}
    class SyntheticArchive:
        def read(self,_,*,cap,optional):return canonical_json(source)
    post={"id":"b"*40,"platform":"mastodon","original_id":"mastodon.example:1234",
          "text":"첫줄 연결"}
    result=viewer._source_ui(SyntheticArchive(),post)
    assert result["sensitive"] is True
    assert result["content_warning"]=="콘텐츠 주의"
    assert result["pinned"] is True
    assert any(p["href"]=="https://valid.example/source" for p in result["rich_text"])
    assert result["poll"]["options"][0]["votes_count"]==3
    assert result["alt_text"]==["텍스트 설명"]
    assert result["engagement"]["replies_count"]==2


def test_source_links_never_accept_javascript_or_internal_network():
    html=viewer._PublicHtmlParts()
    html.feed('<a href="javascript:alert(1)">악성</a><a href="https://public.example">공개</a>')
    assert html.parts[0]["text"]=="악성" and not html.parts[0]["href"]
    assert html.parts[1]["href"]=="https://public.example"


def test_all_mastodon_source_profile_fields_and_paragraphs_render_as_safe_cards():
    """The archived raw provider snapshot, not a flattened summary, owns bio."""
    name="snap-"+"1"*20+"-"+"a"*16+".json"
    identity="mastodon.example:20200"
    doc={"platform":"mastodon","identity":identity,
         "handle":"writer@mastodon.example","display_name":"Public QA",
         "description":"Previously flattened biography",
         "captured_at":"2026-11-16T00:00:00Z",
         "raw":{"note":"<p>first line</p><p>second line</p>",
                "fields":[{"name":"Pronouns","value":"she/her",
                           "verified_at":None},
                          {"name":"Website",
                           "value":'<a href="https://example.org">example.org</a>',
                           "verified_at":"2026-11-16T00:00:00Z"},
                          {"name":"Unsafe marker",
                           "value":'<a href="javascript:alert(1)">No script</a>',
                           "verified_at":None}]},
         "assets":{"avatar":{"status":"not_set"},"banner":{"status":"not_set"}}}
    class PublicSnapshot:
        def names(self,prefix):
            return [name] if prefix=="profile/snapshots" else []
        def read(self,path,*,cap,optional=False):
            return canonical_json(doc) if path=="profile/snapshots/"+name else None
    result=viewer.profile_view(PublicSnapshot(),
       "mastodon-"+"a"*40,
       {"platform":"mastodon","identity":identity,
        "profile_url":"https://mastodon.example/@writer"})
    assert result["description"]=="first line\nsecond line"
    assert result["snapshot_id"]==name
    assert result["latest_snapshot"] is True
    assert len(result["fields_rendered"])==3
    assert result["fields_rendered"][1]["parts"][0]=={
        "text":"example.org","href":"https://example.org"}
    assert result["fields_rendered"][1]["verified_at"]
    assert result["fields_rendered"][2]["parts"][0]["href"]==""
    assert not any("<a" in str(row) for row in result["fields_rendered"])


def test_every_public_source_label_is_retained_in_viewer_audit():
    post={"id":PID,"platform":"bluesky",
          "original_id":"at://"+DID+"/app.bsky.feed.post/test100",
          "text":"Public source returned by PDS"}
    raw={"uri":post["original_id"],
         "value":{"text":post["text"],
                  "labels":{"values":[{"val":"!hide"},
                                      {"val":"!takedown"},
                                      {"val":"user-defined"}]}}}
    class PublicSource:
        def read(self,path,*,cap,optional=False):
            return canonical_json(raw) if path.endswith(PID+".json") else None
    result=viewer._source_ui(PublicSource(),post)
    assert result["source_labels"]==["!hide","!takedown","user-defined"]
    assert result["rich_text"][0]["text"]=="Public source returned by PDS"
