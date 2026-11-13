"""Exact-original attachment staging: immutable source URL, slot and byte SHA."""
import json
import pytest
from demand_archive import sha256,post_key,canonical_json
from demand_capture_job import make_post
from test_demand_archive import FakeCloud,post


def partial(pid,source=None):
    p={**post(),"id":pid,"media_expected":2,"media_saved":1,"archive_complete":False}
    blob=b"synthetic original photo two"
    item={"key":"posts/"+pid+"/media/0002.jpg","mime":"image/jpeg",
          "bytes":len(blob),"sha256":sha256(blob),"remote_verified":True}
    if source is not None:
        item["source_url"]=source
    p["media"]=[item]
    return p,blob


def test_source_url_bound_partial_reuses_only_exact_slot_and_sha():
    cloud=FakeCloud()
    pid=post_key("bluesky","at://did:plc:synthetic/app.bsky.feed.post/source-1")
    url="https://cdn.bsky.app/img/this-post-image-2.jpg"
    p,blob=partial(pid,url)
    cloud.stage_partial_media(p,[blob])
    marker=json.loads(cloud.objects["metadata/media-parts/"+pid+"/0002.json"])
    assert marker["source_url"]==url
    assert cloud.read_staged_media(pid,2,expected_source_url=url)==("image/jpeg",blob)
    assert cloud.read_staged_media(pid,2,expected_source_url="https://cdn.bsky.app/img/different.jpg") is None
    assert cloud.read_staged_media(pid,1,expected_source_url=url) is None
    assert cloud.read_staged_media("b"*40,2,expected_source_url=url) is None
    assert len(cloud.objects)==2,"failed source-mismatch never mutates remote data"


def test_legacy_partial_requires_original_first_observation_url_evidence():
    cloud=FakeCloud()
    pid=post_key("bluesky","at://did:plc:synthetic/app.bsky.feed.post/source-2")
    url1="https://cdn.bsky.app/img/one.jpg"
    url2="https://cdn.bsky.app/img/two.jpg"
    p,blob=partial(pid)
    cloud.stage_partial_media(p,[blob])
    assert cloud.read_staged_media(pid,2,expected_source_url=url2) is None
    first={"id":pid,"platform":"bluesky","text":"synthetic observed post",
           "source_url":"https://bsky.app/profile/synthetic/post/source-2",
           "posted_at":"2026-11-03T00:00:00Z",
           "observed_at":1793667900,"media_links":[url1,url2]}
    cloud.save_first_observation(pid,canonical_json(first))
    assert cloud.read_staged_media(pid,2,expected_source_url=url2)==("image/jpeg",blob)
    assert cloud.read_staged_media(pid,2,expected_source_url=url1) is None
    # Immutable first observation corruption/missing link cannot authorize reuse.
    for key in cloud.first_observation_keys(pid):
        if key in cloud.objects:
            cloud.objects[key]=b'{"media_links":"not a list"}'
    assert cloud.read_staged_media(pid,2,expected_source_url=url2) is None


def test_new_staged_source_rejected_if_not_https():
    cloud=FakeCloud()
    pid=post_key("bluesky","at://did:plc:synthetic/app.bsky.feed.post/source-3")
    p,blob=partial(pid,"javascript:untrusted")
    with pytest.raises(ValueError,match="invalid original attachment source"):
        cloud.stage_partial_media(p,[blob])
    assert cloud.objects=={},"invalid URL should fail before uploading even media"


def test_public_source_retry_cannot_substitute_another_media_url():
    cloud=FakeCloud()
    oid="at://did:plc:synthetic/app.bsky.feed.post/source-4"
    pid=post_key("bluesky",oid)
    old="https://cdn.bsky.app/img/original-2.jpg"
    changed="https://cdn.bsky.app/img/unrelated-2.jpg"
    original=b"synthetic still valid original first slot"
    old_second=b"synthetic stored second slot"
    row={"platform":"bluesky","original_id":oid,
         "source_url":"https://bsky.app/profile/synthetic/post/source-4",
         "posted_at":"2026-11-03T00:00:00Z",
         "text":"synthetic verified public post","profile_url":"",
         "media_urls":["https://cdn.bsky.app/img/original-1.jpg",old],
         "media_expected":2}
    early,blobs=make_post(row,1793667900,get_media=lambda u:("image/jpeg",old_second) if u==old else None,cloud=cloud)
    assert early["media"][0]["source_url"]==old
    cloud.stage_partial_media(early,blobs)
    row["media_urls"][1]=changed
    retry,_=make_post(row,1793667900,get_media=lambda u:("image/jpeg",original) if u.endswith("original-1.jpg") else None,cloud=cloud)
    assert retry["media_saved"]==1 and not retry["archive_complete"]
    assert retry["media"][0]["key"].endswith("/0001.jpg")
    assert "metadata/entries/"+pid+".json" not in cloud.objects


def test_public_bluesky_video_view_is_not_false_100_percent_archive(monkeypatch):
    import demand_capture_job as capture
    from datetime import datetime,timezone
    now=int(datetime(2026,11,4,5,0,tzinfo=timezone.utc).timestamp())
    did="did:plc:syntheticvideoblobrecord"
    cid="bafk"+"a"*45
    url="https://video.bsky.app/watch/"+did+"/"+cid+"/playlist.m3u8"
    original={
        "uri":"at://"+did+"/app.bsky.feed.post/3kltest1234",
        "author":{"did":did,"handle":"qa.bsky.social"},
        "record":{"text":"섹트 video synthetic only",
                  "createdAt":datetime.fromtimestamp(now-30,timezone.utc).isoformat()},
        "embed":{"$type":"app.bsky.embed.video#view","playlist":url,"cid":cid}
    }
    monkeypatch.setattr(capture,"bluesky_public_search",lambda *args:{"posts":[original]})
    rows=list(capture.bluesky("섹트",now-3600,now))
    assert len(rows)==1
    assert rows[0]["media_expected"]==1
    assert rows[0]["media_urls"]==[url]
    assert capture.download_media(url) is None,"HLS manifest is not original MP4"
    post,blobs=capture.make_post(rows[0],now,get_media=lambda _:None)
    assert post["media_expected"]==1
    assert post["media_saved"]==0
    assert post["archive_complete"] is False
    assert blobs==[]
    assert not post["media"]


def test_video_blob_cid_fallback_uses_exact_verified_public_post_did(monkeypatch):
    import demand_capture_job as capture
    from datetime import datetime,timezone
    now=int(datetime(2026,11,4,5,0,tzinfo=timezone.utc).timestamp())
    did="did:plc:syntheticvideoblobrecord"
    cid="bafk"+"a"*45
    original={
        "uri":"at://"+did+"/app.bsky.feed.post/3kltest1234",
        "author":{"did":did,"handle":"qa.bsky.social"},
        "record":{"text":"섹트 second video synthetic",
                  "createdAt":datetime.fromtimestamp(now-30,timezone.utc).isoformat(),
                  "embed":{"$type":"app.bsky.embed.video",
                           "video":{"ref":{"$link":cid},"mimeType":"video/mp4"}}},
        "embed":{"$type":"app.bsky.embed.video#view","playlist":"https://evil.example/irrelevant.m3u8"}
    }
    monkeypatch.setattr(capture,"bluesky_public_search",lambda *args:{"posts":[original]})
    rows=list(capture.bluesky("섹트",now-3600,now))
    assert len(rows)==1
    assert rows[0]["media_urls"]==[
        "https://video.bsky.app/watch/"+did+"/"+cid+"/playlist.m3u8"]
    assert rows[0]["media_expected"]==1

    # An AppView playlist bound to a DIFFERENT actor is not an original
    # belonging to this captured author, even on the trusted video domain.
    original["embed"]["playlist"]=(
        "https://video.bsky.app/watch/did:plc:someotheractor/"+cid+
        "/playlist.m3u8")
    other=list(capture.bluesky("섹트",now-3600,now))
    assert len(other)==1
    assert other[0]["media_urls"]==rows[0]["media_urls"]

    # A valid view CID can independently provide the account-bound playlist
    # if a source record embed is not returned by a partial public API.
    del original["record"]["embed"]
    original["embed"]["cid"]=cid
    view_only=list(capture.bluesky("섹트",now-3600,now))
    assert len(view_only)==1
    assert view_only[0]["media_urls"]==rows[0]["media_urls"]


def test_up_to_sixteen_original_attachments_keep_exact_order_and_extra_remain_missing():
    import demand_capture_job as capture
    media=["https://cdn.bsky.app/img/synthetic"+str(i)+".jpg" for i in range(17)]
    row=capture.normalized("bluesky","at://did:plc:synthetic/app.bsky.feed.post/post16",
        "https://bsky.app/profile/qa.bsky.social/post/post16",
        "섹트 synthetic 17 attachments", "2026-11-04T05:00:00Z", media)
    assert row["media_expected"]==17
    assert row["media_urls"]==media[:16]
    post,blobs=capture.make_post(row,1793768400,
        get_media=lambda url:("image/jpeg",url.encode()))
    assert len(blobs)==16
    assert post["media_saved"]==16
    assert post["archive_complete"] is False,"truncated source must remain incomplete"
    assert [m["key"].split("/")[-1] for m in post["media"]]==[
        f"{n:04d}.jpg" for n in range(1,17)]
    row16=dict(row,media_urls=row["media_urls"],media_expected=16)
    complete,_=capture.make_post(row16,1793768400,
        get_media=lambda url:("image/jpeg",url.encode()))
    assert complete["archive_complete"] is True
    assert [m["source_url"] for m in complete["media"]]==media[:16]




def test_lemmy_capture_uses_actual_source_image_never_generated_thumbnail(monkeypatch):
    import demand_capture_job as capture
    from datetime import datetime,timezone
    now=int(datetime(2026,11,4,6,0,tzinfo=timezone.utc).timestamp())
    iso=datetime.fromtimestamp(now-60,timezone.utc).isoformat()
    original="https://pictrs.lemmy.world/image/synthetic-original123.jpg"
    thumbnail="https://pictrs.lemmy.world/image/synthetic-cropped-preview.jpg"
    post={
        "id":911,"ap_id":"https://lemmy.world/post/911","name":"섹트 public example",
        "published":iso,"url":original,"thumbnail_url":thumbnail
    }
    monkeypatch.setattr(capture,"get_json",lambda url,body=None:{"posts":[{"post":post}]})
    rows=list(capture.lemmy("섹트",now-3600,now))
    assert len(rows)==1
    assert rows[0]["media_urls"]==[original]
    assert rows[0]["media_expected"]==1
    post["url"]="https://lemmy.world/post/911"
    rows=list(capture.lemmy("섹트",now-3600,now))
    assert len(rows)==1
    assert rows[0]["media_urls"]==[], "never substitute generated thumbnail for source original"
    assert thumbnail not in rows[0]["media_urls"]
    post["url"]="https://pictrs.lemmy.world/image/extensionless_original"
    rows=list(capture.lemmy("섹트",now-3600,now))
    assert rows[0]["media_urls"]==[post["url"]], "original pictrs link may have no extension"


def test_unrelated_lemmy_thumbnail_cannot_become_first_original_attachment(monkeypatch):
    import demand_capture_job as capture
    from datetime import datetime,timezone
    now=int(datetime(2026,11,4,6,0,tzinfo=timezone.utc).timestamp())
    iso=datetime.fromtimestamp(now-60,timezone.utc).isoformat()
    record={"id":912,"ap_id":"https://lemmy.world/post/912",
            "name":"섹트 synthetic external blog",
            "published":iso,
            "url":"https://example.org/article/912",
            "thumbnail_url":"https://pictrs.lemmy.world/image/generated.jpg"}
    monkeypatch.setattr(capture,"get_json",lambda *a,**kw:{"posts":[{"post":record}]})
    rows=list(capture.lemmy("섹트",now-3600,now))
    assert len(rows)==1
    assert rows[0]["media_urls"]==[]
    post,blobs=capture.make_post(rows[0],now,get_media=lambda url:
        (_ for _ in ()).throw(AssertionError("no unrelated thumbnail download")))
    assert post["media_saved"]==0
    assert post["media"]==[]
    assert blobs==[]



def test_public_bluesky_video_original_is_accepted_only_when_pds_cid_sha_matches(
        monkeypatch):
    """One original MP4, not the HLS playlist or its thumbnail."""
    import base64
    import hashlib
    import demand_capture_job as capture
    from urllib.parse import urlsplit,parse_qs
    did="did:plc:abcdefghijklmnopqrstuvwx"
    raw=b"SYNTHETIC original authored mp4 bytes for hash verification"
    cid="b"+base64.b32encode(
        bytes([1,85,18,32])+hashlib.sha256(raw).digest()).decode().lower().rstrip("=")
    assert capture.blob_sha256_from_cid(cid)==hashlib.sha256(raw).digest()
    assert capture.blob_sha256_from_cid("baf-not-a-real-cid") is None
    playlist="https://video.bsky.app/watch/"+did+"/"+cid+"/playlist.m3u8"
    monkeypatch.setenv("DEMAND_BSKY_PDS_BLOB_ORIGINALS","1")
    class Response:
        def __init__(self,payload,mime):
            self.data=payload
            self.headers={"Content-Type":mime}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):return self.data[:limit]
    class PublicPDS:
        def __init__(self,blob):
            self.blob=blob
            self.requests=[]
        def open(self,request,timeout):
            url=request.full_url
            self.requests.append(url)
            if url.startswith("https://plc.directory/"):
                return Response(json.dumps({"id":did,"service":[{
                    "type":"AtprotoPersonalDataServer",
                    "serviceEndpoint":"https://bsky.social"}]}).encode(),"application/json")
            if url.startswith("https://bsky.social/xrpc/com.atproto.sync.getBlob"):
                qs=parse_qs(urlsplit(url).query)
                assert qs=={"did":[did],"cid":[cid]}
                return Response(self.blob,"video/mp4")
            raise AssertionError("unsafe provider URL attempted")
    remote=PublicPDS(raw)
    monkeypatch.setattr(capture,"MEDIA_OPENER",remote)
    now=1793667900
    row={"uri":"at://"+did+"/app.bsky.feed.post/abc123",
         "author":{"did":did},
         "record":{"text":"섹트 synthetic public test",
                   "createdAt":"2026-11-03T00:55:00Z",
                   "embed":{"$type":"app.bsky.embed.video",
                            "video":{"ref":{"$link":cid}}}},
         "embed":{"$type":"app.bsky.embed.video#view",
                  "cid":cid,"playlist":playlist}}
    monkeypatch.setattr(capture,"bluesky_public_search",lambda *_:{"posts":[row]})
    results=list(capture.bluesky("섹트",now-3600,now))
    assert len(results)==1
    video_url=results[0]["media_urls"][0]
    assert video_url.startswith("https://bsky.social/xrpc/com.atproto.sync.getBlob?")
    assert capture.media_allowed(video_url)
    p,blobs=capture.make_post(results[0],now)
    assert p["archive_complete"] is True and p["media_saved"]==p["media_expected"]==1
    assert p["media"][0]["mime"]=="video/mp4"
    assert blobs==[raw]
    assert p["media"][0]["sha256"]==hashlib.sha256(raw).hexdigest()
    assert capture.download_media(video_url)==("video/mp4",raw)
    # If the PDS serves the wrong bytes for a correct CID, never count it.
    remote.blob=b"different-transcoded-video-not-original"
    assert capture.download_media(video_url) is None
    assert not capture.media_allowed(video_url.replace("bsky.social","evil.example"))
    assert len(remote.requests)>=3


def test_bluesky_video_untrusted_or_unreachable_pds_remains_incomplete(
        monkeypatch):
    import base64
    import hashlib
    import demand_capture_job as capture
    did="did:plc:abcdefghijklmnopqrstuvwx"
    cid="b"+base64.b32encode(
        bytes([1,85,18,32])+hashlib.sha256(b"qa").digest()).decode().lower().rstrip("=")
    monkeypatch.setenv("DEMAND_BSKY_PDS_BLOB_ORIGINALS","1")
    class Response:
        def __init__(self,payload):self.payload=payload
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):return self.payload[:limit]
    class Untrusted:
        def open(self,*args,**kwargs):
            return Response(json.dumps({"id":did,"service":[{
                "type":"AtprotoPersonalDataServer",
                "serviceEndpoint":"https://127.0.0.1"}]}).encode())
    monkeypatch.setattr(capture,"MEDIA_OPENER",Untrusted())
    playlist="https://video.bsky.app/watch/"+did+"/"+cid+"/playlist.m3u8"
    row={"uri":"at://"+did+"/app.bsky.feed.post/abc123",
         "author":{"did":did},
         "record":{"text":"섹트 synthetic public test",
                   "createdAt":"2026-11-03T00:55:00Z",
                   "embed":{"$type":"app.bsky.embed.video",
                            "video":{"ref":{"$link":cid}}}},
         "embed":{"$type":"app.bsky.embed.video#view",
                  "cid":cid,"playlist":playlist}}
    monkeypatch.setattr(capture,"bluesky_public_search",lambda *_:{"posts":[row]})
    now=1793667900
    results=list(capture.bluesky("섹트",now-3600,now))
    assert len(results)==1 and results[0]["media_urls"]==[playlist]
    p,blobs=capture.make_post(results[0],now)
    assert p["archive_complete"] is False
    assert p["media_expected"]==1 and p["media_saved"]==0 and blobs==[]
