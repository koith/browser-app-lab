"""Synthetic public-account history QA: no network, private accounts or user data."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from test_demand_archive import FakeCloud
import target_account_archive as job

DID="did:plc:"+"a"*24
PHOTO=b"original PDS image bytes -- synthetic only"
VIDEO=b"original PDS MP4 bytes -- synthetic only"
AUDIO=b"synthetic public account original audio bytes"


def cid(data):
    raw=b"\x01\x55\x12\x20"+hashlib.sha256(data).digest()
    return "b"+base64.b32encode(raw).decode().lower().rstrip("=")


def blue_row(rkey,text,*,reply=False,assets=None):
    values={"$type":"app.bsky.feed.post","createdAt":"2026-11-03T12:00:00Z",
            "text":text}
    if reply:
        values["reply"]={"parent":{"uri":"at://did:plc:"+"b"*24+
                                 "/app.bsky.feed.post/parent"},
                         "root":{"uri":"at://did:plc:"+"b"*24+
                                "/app.bsky.feed.post/parent"}}
    if assets:
        values["embed"]={"$type":"app.bsky.embed.images","items":[{
            "image":{"$type":"blob","mimeType":mime,"ref":{"$link":cid(blob)},
                     "size":len(blob)}} for mime,blob in assets]}
    return {"uri":"at://"+DID+"/app.bsky.feed.post/"+rkey,
            "cid":cid(text.encode()),"value":values}


class BlueAPI:
    def __init__(self, pages):
        self.pages=pages
        self.blobs={cid(blob):(mime,blob) for page in pages.values()
                    for row in page[0] for mime,blob in getattr(row,"_files",[])}
        self.calls=[]

    def json(self,url,body=None):
        self.calls.append(url)
        if "app.bsky.actor.getProfile" in url:
            return {"did":DID,"handle":"qa-example.bsky.social",
                    "displayName":"QA account","description":"Archived public biography",
                    "avatar":"https://cdn.bsky.app/img/qa-avatar",
                    "followersCount":1,"followsCount":1,"postsCount":2}
        if "com.atproto.repo.getRecord" in url:
            return {"value":{"avatar":{
                "$type":"blob","mimeType":"image/jpeg",
                "ref":{"$link":cid(PHOTO)},"size":len(PHOTO)}}}
        if "app.bsky.graph.getFollowers" in url:
            return {"followers":[{"did":"did:plc:"+"b"*24,
                                   "handle":"reader.bsky.social",
                                   "displayName":"Public reader"}]}
        if "app.bsky.graph.getFollows" in url:
            return {"follows":[{"did":"did:plc:"+"c"*24,
                                "handle":"friend.bsky.social",
                                "displayName":"Public friend"}]}
        if "app.bsky.feed.getPostThread" in url:
            target=parse_qs(urlsplit(url).query).get("uri",[""])[0]
            own=next((row for page in self.pages.values() for row in page[0]
                      if row["uri"]==target),None)
            if own is None:
                raise job.SourceUnavailable("public thread unavailable")
            reply={"post":{"uri":"at://did:plc:"+"b"*24+
                                    "/app.bsky.feed.post/comment1",
                           "author":{"did":"did:plc:"+"b"*24,
                                     "handle":"reader.bsky.social"},
                           "record":{"text":"Public comment synthetic",
                                     "createdAt":"2026-11-03T12:05:00Z"}}}
            return {"thread":{"post":{"uri":target},"replies":[reply]}}
        if url.startswith("https://plc.directory/"):
            return {"service":[{"id":"#atproto_pds",
                    "serviceEndpoint":"https://pds.testing.example"}]}
        if "com.atproto.repo.listRecords" in url:
            cursor=parse_qs(urlsplit(url).query).get("cursor",[None])[0]
            rows,nxt=self.pages[cursor]
            return {"records":rows,"cursor":nxt} if nxt else {"records":rows}
        raise AssertionError("unexpected provider request: "+url)

    def media(self,url,mime):
        handle=parse_qs(urlsplit(url).query)["cid"][0]
        for item in self.blobs.values():
            if cid(item[1])==handle:
                return mime,item[1]
        raise job.SourceUnavailable("synthetic missing original")


class MastodonAPI:
    def __init__(self, statuses):
        self.statuses=statuses
        self.calls=[]

    def json(self,url,body=None):
        self.calls.append(url)
        if "/api/v1/accounts/lookup" in url:
            return {"id":"20200","acct":"writer","url":"https://mastodon.example/@writer"}
        if "/api/v1/accounts/20200" in url and "/statuses?" not in url and "/followers" not in url and "/following" not in url:
            return {"id":"20200","acct":"writer","display_name":"Public writer",
                    "note":"<p>Archived profile about</p>",
                    "followers_count":1,"following_count":1,"statuses_count":2}
        if "/api/v1/statuses/" in url and "/context" in url:
            return {"ancestors":[],"descendants":[{
                "id":"890","visibility":"public","account":{"id":"20201","acct":"commenter"},
                "created_at":"2026-11-03T12:10:00Z",
                "content":"<p>Public reply to writer</p>",
                "media_attachments":[]}]}
        if "/statuses?" in url:
            if "max_id=" in url:
                return []
            return self.statuses
        raise AssertionError("unexpected provider request: "+url)

    def json_with_headers(self,url):
        if "/followers" in url or "/following" in url:
            return ([{"id":"20201","acct":"public-reader","display_name":"Public",
                      "url":"https://mastodon.example/@public-reader"}],{})
        raise AssertionError("unexpected social graph endpoint")

    def media(self,url,mime):
        if url.endswith(".mp3"):
            return "audio/mpeg",AUDIO
        raise job.SourceUnavailable("synthetic unsupported media")


@pytest.fixture(autouse=True)
def fake_private_archive(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-private-cookie")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def test_blue_source_replies_and_video_original_bytes_are_verified_and_resume(capsys):
    p1=blue_row("original01","A public synthetic initial post",
                assets=[("image/jpeg",PHOTO),("video/mp4",VIDEO)])
    p2=blue_row("original02","A public synthetic reply",reply=True)
    api=BlueAPI({None:([p1],"page-two"),"page-two":([p2],None)})
    api.blobs={cid(PHOTO):("image/jpeg",PHOTO),cid(VIDEO):("video/mp4",VIDEO)}
    cloud=FakeCloud()
    first=job.run_one("bluesky","qa-example.bsky.social",
                      root=cloud,api=api,max_pages=1,clock=lambda:0)
    assert first["posts_verified"]==1 and first["status"]=="RESUME_NEEDED"
    second=job.run_one("bluesky","qa-example.bsky.social",
                       root=cloud,api=api,max_pages=2,clock=lambda:0)
    assert second["posts_verified"]==1
    assert second["status"]=="COMPLETE_CURRENT_PUBLIC_CURSOR"
    root="account-archives/bluesky/"+job.archive_key(job.resolve("bluesky",DID,api))
    archive=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    stored=[json.loads(archive.read("posts/"+job.post_key("bluesky",p["uri"])+"/post.json"))
            for p in (p1,p2)]
    assert len(stored)==2
    latest=next(p for p in stored if p["kind"]=="post")
    assert latest["media_expected"]==2
    assert latest["media_saved"]==2
    assert all(m["remote_verified"] for m in latest["media"])
    assert any(m["kind"]=="video" for m in latest["media"])
    assert any(p["kind"]=="reply" and p["reply_to"] for p in stored)
    archive=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    assert archive.read_verified(latest["media"][0]["key"],
                                 latest["media"][0]["sha256"],cap=len(PHOTO)+1)==PHOTO
    assert archive.read_verified(latest["media"][1]["key"],
                                 latest["media"][1]["sha256"],cap=len(VIDEO)+1)==VIDEO
    assert all(archive.shared_record_key(m["key"]) in cloud.objects
               for m in latest["media"])
    assert len(archive.names("metadata/source-records"))==2
    assert len(archive.names("metadata/checkpoints"))==2
    profiles=[json.loads(archive.read("profile/snapshots/"+name))
              for name in archive.names("profile/snapshots")]
    assert profiles[-1]["description"]=="Archived public biography"
    assert profiles[-1]["assets"]["avatar"]["status"]=="sha256_verified"
    assert profiles[-1]["followers_count"]==1
    assert len(archive.names("graph/pages"))==4
    assert sum(len(archive.names("threads/"+job.post_key("bluesky",p["uri"])))
               for p in (p1,p2))==2
    assert len(archive.names("thread-markers"))==2
    thread=[json.loads(archive.read("threads/"+pid+"/"+name))
            for pid in (job.post_key("bluesky",p["uri"]) for p in (p1,p2))
            for name in archive.names("threads/"+pid)]
    assert thread[0]["replies"][0]["text"]=="Public comment synthetic"
    assert "qa-example" not in capsys.readouterr().out


def test_mastodon_author_posts_replies_and_audio_are_verified():
    records=[{"id":"900","account":{"id":"20200"},"visibility":"public",
              "sensitive":False,"reblog":None,
              "url":"https://mastodon.example/@writer/900",
              "created_at":"2026-11-03T12:00:00Z","content":"<p>Public reply with sound</p>",
              "in_reply_to_id":"700","media_attachments":[
                  {"type":"audio","url":"https://media.mastodon.example/file.mp3"}]},
             {"id":"899","account":{"id":"20200"},"visibility":"followers",
              "created_at":"2026-11-03T12:00:00Z","content":"private",
              "media_attachments":[]},
             {"id":"898","account":{"id":"90909"},"visibility":"public",
              "created_at":"2026-11-03T12:00:00Z","content":"not target",
              "media_attachments":[]}]
    cloud=FakeCloud()
    api=MastodonAPI(records)
    result=job.run_one("mastodon","writer@mastodon.example",root=cloud,
                       api=api,max_pages=2,clock=lambda:0)
    assert result["posts_verified"]==1 and result["status"]=="COMPLETE_CURRENT_PUBLIC_CURSOR"
    archive=job.account_cloud(cloud,job.resolve("mastodon","writer@mastodon.example",api))
    key="posts/"+job.post_key("mastodon","mastodon.example:20200:900")+"/post.json"
    a=[json.loads(archive.read(key))]
    assert len(a)==1 and a[0]["kind"]=="reply"
    assert a[0]["media"][0]["mime"]=="audio/mpeg"
    assert a[0]["text"]=="Public reply with sound"
    assert all("private" not in str(x) for x in a)


def test_exact_original_blob_CID_hash_rejects_substitution_without_checkpoint():
    p=blue_row("wrongmedia","source text",assets=[("image/jpeg",PHOTO)])
    class WrongMedia(BlueAPI):
        def media(self,url,mime):
            return mime,b"wrong CDN-transformed bytes"
    api=WrongMedia({None:([p],None)})
    cloud=FakeCloud()
    with pytest.raises(job.SourceUnavailable,match="original media incomplete"):
        job.run_one("bluesky",DID,root=cloud,api=api,max_pages=1,clock=lambda:0)
    archive=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    assert not archive.names("metadata/checkpoints")
    assert len(archive.names("metadata/source-records"))==1
    assert not archive.names("metadata/entries")


def test_missing_account_and_private_source_fail_closed():
    for platform,account in [("mastodon","user@127.0.0.1"),
                             ("mastodon","https://localhost/@user"),
                             ("bluesky","https://evil.example/profile/user"),
                             ("bluesky","did:plc:bad")]:
        with pytest.raises(ValueError):
            job.profile_input(platform,account)
    with pytest.raises(ValueError):
        job.require_public_https("http://localhost:9999/metadata")
    with pytest.raises(ValueError):
        job.require_public_https("https://127.0.0.1/secret")


def test_replay_same_completed_account_does_not_duplicate_post_or_media():
    post=blue_row("once-only","confirmed public content")
    api=BlueAPI({None:([post],None)})
    cloud=FakeCloud()
    job.run_one("bluesky",DID,root=cloud,api=api,max_pages=1,clock=lambda:0)
    archive=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    key="posts/"+job.post_key("bluesky",post["uri"])+"/post.json"
    before=archive.read(key)
    result=job.run_one("bluesky",DID,root=cloud,api=api,max_pages=1,clock=lambda:0)
    assert result["previously_saved"]==1
    assert archive.read(key)==before


def test_cid_sha256_is_raw_original_not_cdn_derivative():
    assert job.cid_sha256(cid(PHOTO))==hashlib.sha256(PHOTO).hexdigest()
    with pytest.raises(ValueError):
        job.cid_sha256("not-a-cid")


def test_account_cloud_namespace_separates_two_public_profiles():
    root=FakeCloud()
    p1={"platform":"bluesky","identity":DID}
    p2={"platform":"bluesky","identity":"did:plc:"+"b"*24}
    assert job.account_cloud(root,p1).remote!=job.account_cloud(root,p2).remote
    assert "account-archives" in job.account_cloud(root,p1).remote


def test_empty_registered_schedule_is_not_a_successful_backup(capsys):
    """Green scheduled Actions runs must not claim an archive with zero targets."""
    cloud=FakeCloud()
    with pytest.raises(RuntimeError,match="no registered public accounts"):
        job.run_registered(root=cloud)
    output=capsys.readouterr().out
    assert "TARGET_ACCOUNT_ARCHIVE_SCHEDULE" in output
    assert '"registered": 0' in output
    assert '"processed": 0' in output
    assert '"state": "NO_REGISTERED_TARGETS"' in output
    assert not any("/account-archives/" in path for path in cloud.objects)


def test_reviewed_bootstrap_retries_first_registration_with_remote_verification(tmp_path,capsys):
    """A failed first dispatch is retried by schedule without a false-green no-op."""
    request=tmp_path/"selected.json"
    request.write_text(json.dumps({"schema_version":1,"platform":"bluesky",
                                   "account":"qa-example.bsky.social","max_pages":1}))
    post=blue_row("bootstrap01","synthetic public original")
    cloud=FakeCloud()
    api=BlueAPI({None:([post],None)})
    job.run_registered(root=cloud,api=api,bootstrap=True,bootstrap_path=request)
    assert any("metadata/target-accounts/" in name for name in cloud.objects)
    archive=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    assert archive.names("metadata/entries")
    assert len(archive.load_catalog())==1
    assert '"initial_registration": true' in capsys.readouterr().out.lower()


def test_reviewed_bootstrap_does_not_accept_unvalidated_config(tmp_path):
    path=tmp_path/"selected.json"
    path.write_text(json.dumps({"schema_version":1,"platform":"bluesky",
                                "account":"qa-example.bsky.social",
                                "max_pages":2,"surprise":"untrusted"}))
    with pytest.raises(ValueError,match="invalid reviewed target"):
        job.read_bootstrap_request(path)


def test_shallow_private_media_recovers_when_nested_copyto_is_missing():
    """The exact original is SHA-read back, even if nested upload paths fail."""
    p=blue_row("missingfolder","synthetic exact source",
               assets=[("image/jpeg",PHOTO)])
    api=BlueAPI({None:([p],None)})
    api.blobs={cid(PHOTO):("image/jpeg",PHOTO)}
    cloud=FakeCloud()
    base_runner=cloud.runner
    attempted=[]
    def reject_nested_upload(args,data=None,timeout=150,allow_missing=False):
        if (args[0] in ("copyto","rcat")
                and any("/account-archives/" in str(x) and
                        "/media/" in str(x) for x in args)):
            attempted.append(args[0])
            raise RuntimeError("private cloud copyto failed (missing)")
        return base_runner(args,data=data,timeout=timeout,allow_missing=allow_missing)
    cloud.runner=reject_nested_upload
    report=job.run_one("bluesky",DID,root=cloud,api=api,max_pages=1,clock=lambda:0)
    assert report["posts_verified"]==1
    assert report["status"]=="COMPLETE_CURRENT_PUBLIC_CURSOR"
    resolved=job.resolve("bluesky",DID,api)
    archive=job.account_cloud(cloud,resolved)
    key="posts/"+job.post_key("bluesky",p["uri"])+"/media/0001.jpg"
    shallow=archive.shared_media_key(key)
    flat=archive.shared_record_key(key)
    assert flat in cloud.objects
    assert cloud.objects[flat]==PHOTO
    assert archive.read_verified(key,job.sha256(PHOTO),cap=len(PHOTO)+1)==PHOTO
    assert not attempted,"depth-one account records must avoid nested upload paths"


def test_shallow_media_namespace_is_account_and_slot_scoped():
    root=FakeCloud()
    p1={"platform":"bluesky","identity":DID}
    p2={"platform":"bluesky","identity":"did:plc:"+"b"*24}
    key="posts/"+"a"*40+"/media/0001.jpg"
    a=job.account_cloud(root,p1)
    b=job.account_cloud(root,p2)
    assert a.shared_media_key(key)!=b.shared_media_key(key)
    assert a.shared_media_key(key)!=a.shared_media_key(key.replace("0001","0002"))
    assert a.shared_media_key("../../unsafe") is None


def test_all_account_object_types_ignore_nested_upload_failure():
    """Metadata, checkpoints, graph, thread and original media share one flat gate."""
    cloud=FakeCloud()
    original_runner=cloud.runner
    blocked=[]
    def nested_broken(args,data=None,timeout=150,allow_missing=False):
        if args[0] in ("copyto","rcat") and any(
                "/account-archives/" in str(arg) for arg in args):
            blocked.append(args[0])
            raise RuntimeError("private cloud copyto failed (missing)")
        return original_runner(args,data=data,timeout=timeout,allow_missing=allow_missing)
    cloud.runner=nested_broken
    p=blue_row("allobjects","test post",assets=[("image/jpeg",PHOTO)])
    api=BlueAPI({None:([p],None)})
    api.blobs={cid(PHOTO):("image/jpeg",PHOTO)}
    report=job.run_one("bluesky",DID,root=cloud,api=api,max_pages=1,clock=lambda:0)
    assert report["posts_verified"]==1
    assert report["pages_verified"]==1
    archive=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    for folder in ("metadata/source-records","metadata/checkpoints",
                   "metadata/entries","profile/snapshots","graph/pages",
                   "threads/"+job.post_key("bluesky",p["uri"])):
        assert archive.names(folder),folder
    assert len(archive.load_catalog())==1
    assert not blocked
    # Fresh independently constructed reader discovers the remote records.
    fresh=job.account_cloud(cloud,job.resolve("bluesky",DID,api))
    assert len(fresh.load_catalog())==1
    assert fresh.names("metadata/checkpoints")==["page-00000001.json"]


def test_shallow_account_record_detects_legacy_canonical_collision():
    cloud=FakeCloud()
    account=job.account_cloud(cloud,{"platform":"bluesky","identity":DID})
    key="metadata/source-records/"+"a"*40+".json"
    old=account.remote.split("archive:DemandResearch/",1)[1]+"/"+key
    cloud.objects[old]=b"other original"
    with pytest.raises(RuntimeError,match="checksum collision"):
        account.write_immutable(key,b"proposed original")
    assert account.shared_record_key(key) not in cloud.objects
