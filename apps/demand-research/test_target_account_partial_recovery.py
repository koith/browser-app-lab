"""Synthetic P0: preserve proved public bytes, never call a partial ZIP complete."""
import json
import zipfile
import pytest

import target_account_bundle as bundler
from target_account_archive import SourceUnavailable, run_one, archive_key, resolve
from test_target_account_archive import BlueAPI, blue_row, DID


def _fake_uploader(seen):
    def send(package, *, run_id, account_hash):
        with zipfile.ZipFile(package) as archive:
            manifest=json.loads(archive.read("bundle-manifest.json"))
            seen.append(manifest)
            assert manifest["capture_state"]=="SOURCE_PARTIAL"
            assert all(archive.read(obj["key"]) for obj in manifest["objects"])
        return {"state":"SYNTHETIC_SHA_ONLY","bytes":package.stat().st_size}
    return send


def test_abort_after_post_staging_keeps_originals_as_partial(monkeypatch):
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","")
    monkeypatch.setenv("DEMAND_REQUIRE_PROFILE_SNAPSHOT","1")
    api=BlueAPI({None:([blue_row("sample001","safe public test post")],None)})
    originals=[]
    def broken_run(platform,account,*,root,api,max_pages,archive_factory):
        profile=resolve(platform,account,api)
        root.write_immutable("metadata/target-accounts/" + platform +
                             "-"+archive_key(profile)+".json",b'{"schema":1}')
        archive=archive_factory(root,profile)
        archive.write_immutable("profile/snapshots/snap-00000000000000000001-aaaaaaaaaaaaaaaa.json",
                                b'{"verified":true}')
        archive.write_immutable("posts/original001/post.json",b'{"verified":true}')
        print("TARGET_ACCOUNT_ARCHIVE_AGGREGATE "+
              json.dumps({"profile_verified":True,"posts_verified":1,
                          "media_pending_total":0}))
        raise SourceUnavailable("synthetic PDS pagination failed")
    monkeypatch.setattr(bundler,"run_one",broken_run)
    result=bundler.execute_bundle(
        selected={"platform":"bluesky","account":"qa-example.bsky.social",
                  "max_pages":1},
        api=api,run_id="123456789",cloud_check=False,
        uploader=_fake_uploader(originals))
    assert result["remote_sha256_verified"] is True
    assert result["source_state"]=="SOURCE_PARTIAL"
    assert result["source_partial"] is True
    assert result["public_posts_in_bundle"]==1
    assert result["profile_snapshot_verified"] is True
    assert originals and len(originals[0]["objects"])>=2


def test_profile_outage_does_not_discard_verified_public_post(monkeypatch):
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","")
    monkeypatch.setenv("DEMAND_REQUIRE_PROFILE_SNAPSHOT","1")
    api=BlueAPI({None:([blue_row("sample002","public post survives")],None)})
    seen=[]
    def post_without_profile(platform,account,*,root,api,max_pages,archive_factory):
        profile=resolve(platform,account,api)
        root.write_immutable("metadata/target-accounts/" + platform +
                             "-"+archive_key(profile)+".json",b'{"schema":1}')
        archive=archive_factory(root,profile)
        archive.write_immutable("posts/snapshot002/post.json",b'{"post":true}')
        return {"status":"COMPLETE_CURRENT_PUBLIC_CURSOR",
                "profile":{"profile_verified":False,"profile_assets_unavailable":2},
                "media_pending_total":0,"graph":{},"threads":{"threads_pending":True}}
    monkeypatch.setattr(bundler,"run_one",post_without_profile)
    result=bundler.execute_bundle(
        selected={"platform":"bluesky","account":"qa-example.bsky.social",
                  "max_pages":1},api=api,run_id="123456789",
        cloud_check=False,uploader=_fake_uploader(seen))
    assert result["source_state"]=="SOURCE_PARTIAL"
    assert result["profile_snapshot_verified"] is False
    assert result["public_posts_in_bundle"]==1


def test_registration_only_failed_capture_cannot_be_uploaded(monkeypatch):
    monkeypatch.setenv("DEMAND_ACCOUNT_TEMP_STORAGE","")
    monkeypatch.setenv("DEMAND_REQUIRE_PROFILE_SNAPSHOT","1")
    api=BlueAPI({None:([],None)})
    def only_registration(platform,account,*,root,api,max_pages,archive_factory):
        profile=resolve(platform,account,api)
        root.write_immutable("metadata/target-accounts/" + platform +
                             "-"+archive_key(profile)+".json",b'{"schema":1}')
        raise SourceUnavailable("public source gone")
    monkeypatch.setattr(bundler,"run_one",only_registration)
    def never_upload(*args,**kwargs):
        raise AssertionError("Empty capture must never reach an uploader")
    with pytest.raises(RuntimeError,match="No independently captured"):
        bundler.execute_bundle(
            selected={"platform":"bluesky","account":"qa-example.bsky.social",
                      "max_pages":1},
            api=api,run_id="123456789",cloud_check=False,
            uploader=never_upload)


def test_run_one_keeps_public_history_when_profile_api_unavailable(monkeypatch):
    monkeypatch.setenv("DEMAND_REQUIRE_PROFILE_SNAPSHOT","1")
    class PartialAPI(BlueAPI):
        def __init__(self,pages):
            super().__init__(pages)
            self.profile_lookups=0
        def json(self,url,body=None):
            if "app.bsky.actor.getProfile" in url:
                self.profile_lookups+=1
                if self.profile_lookups>1:
                    raise SourceUnavailable("synthetic public AppView unavailable")
            if "com.atproto.repo.getRecord" in url:
                raise SourceUnavailable("synthetic PDS profile unavailable")
            return super().json(url,body)
    api=PartialAPI({None:([blue_row("sample003","public original available")],None)})
    store=bundler.BundleStore()
    root=bundler.BundleCloud(store)
    result=run_one("bluesky","qa-example.bsky.social",root=root,api=api,
                   max_pages=1,archive_factory=lambda _root,profile:
                       bundler.BundleCloud(store,
                           "account-archives/bluesky/"+archive_key(profile)+"/"))
    assert result["status"]=="SOURCE_PARTIAL"
    assert result["profile"]["profile_verified"] is False
    assert any(k.endswith("/post.json") for k in store.objects)
