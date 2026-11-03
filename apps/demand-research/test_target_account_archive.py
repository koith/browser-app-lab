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
            return {"did":DID,"handle":"qa-example.bsky.social"}
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
        if "/statuses?" in url:
            if "max_id=" in url:
                return []
            return self.statuses
        raise AssertionError("unexpected provider request: "+url)

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
    stored=[json.loads(v) for k,v in cloud.objects.items()
            if k.startswith(root+"/posts/") and k.endswith("/post.json")]
    assert len(stored)==2
    latest=next(p for p in stored if p["kind"]=="post")
    assert latest["media_expected"]==2
    assert latest["media_saved"]==2
    assert all(m["remote_verified"] for m in latest["media"])
    assert any(m["kind"]=="video" for m in latest["media"])
    assert any(p["kind"]=="reply" and p["reply_to"] for p in stored)
    assert cloud.objects[root+"/"+latest["media"][0]["key"]]==PHOTO
    assert cloud.objects[root+"/"+latest["media"][1]["key"]]==VIDEO
    assert len([k for k in cloud.objects if k.startswith(root+"/metadata/source-records/")])==2
    assert len([k for k in cloud.objects if k.startswith(root+"/metadata/checkpoints/")])==2
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
    a=[json.loads(v) for k,v in cloud.objects.items() if k.endswith("/post.json")]
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
    assert not any("/metadata/checkpoints/" in k for k in cloud.objects)
    assert any("/metadata/source-records/" in k for k in cloud.objects)
    assert not any(k.endswith("/post.json") for k in cloud.objects)


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
    before={k:v for k,v in cloud.objects.items() if "/posts/" in k}
    result=job.run_one("bluesky",DID,root=cloud,api=api,max_pages=1,clock=lambda:0)
    assert result["previously_saved"]==1
    assert {k:v for k,v in cloud.objects.items() if "/posts/" in k}==before


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
