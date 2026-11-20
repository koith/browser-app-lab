"""Official public AppView fallback remains source-labeled and DID-bound."""
import json
from urllib.parse import parse_qs,urlsplit

import pytest

import target_account_archive as archive
import target_account_bundle as bundle
from test_target_account_archive import BlueAPI, blue_row, DID


class PdsUnavailable(BlueAPI):
    def __init__(self):
        self.row=blue_row("recovery001","Public original replication")
        super().__init__({None:([self.row],None)})
        self.feed_calls=0

    def json(self,url,body=None):
        if "com.atproto.repo.listRecords" in url:
            raise archive.SourceUnavailable("public PDS temporarily down")
        if "app.bsky.feed.getAuthorFeed" in url:
            self.feed_calls+=1
            return {"feed":[{"post":{
                "uri":self.row["uri"],"cid":self.row["cid"],
                "author":{"did":DID},
                "record":self.row["value"]}}]}
        return super().json(url,body)


def test_live_pds_outage_uses_did_verified_appview_replica(monkeypatch):
    monkeypatch.setenv("DEMAND_REQUIRE_PROFILE_SNAPSHOT","1")
    api=PdsUnavailable()
    store=bundle.BundleStore()
    root=bundle.BundleCloud(store)
    result=archive.run_one("bluesky","qa-example.bsky.social",
        root=root,api=api,max_pages=1,
        archive_factory=lambda _root,profile:bundle.BundleCloud(
          store,"account-archives/bluesky/"+archive.archive_key(profile)+"/"))
    assert result["status"]=="SOURCE_PARTIAL"
    assert result["posts_verified"]==1
    assert api.feed_calls==1
    posts=[json.loads(raw) for key,raw in store.objects.items()
           if key.endswith("/post.json")]
    assert len(posts)==1
    assert posts[0]["source_tier"]=="public_appview_replica"
    assert any("/metadata/source-records/" in key for key in store.objects)


def test_public_appview_does_not_accept_post_by_other_identity():
    class WrongActor(PdsUnavailable):
        def json(self,url,body=None):
            if "app.bsky.feed.getAuthorFeed" in url:
                item={"uri":self.row["uri"],"cid":self.row["cid"],
                      "author":{"did":"did:plc:"+"z"*24},
                      "record":self.row["value"]}
                return {"feed":[{"post":item}],"cursor":"more"}
            return super().json(url,body)
    api=WrongActor()
    resolved=archive.resolve("bluesky","qa-example.bsky.social",api)
    with pytest.raises(archive.SourceUnavailable,
                       match="unavailable from PDS and AppView"):
        archive.page_records(resolved,None,api)


def test_appview_cursor_is_never_passed_to_authoritative_pds():
    class Paginated(PdsUnavailable):
        def json(self,url,body=None):
            if "app.bsky.feed.getAuthorFeed" in url:
                self.feed_calls+=1
                cursor=parse_qs(urlsplit(url).query).get("cursor",[None])[0]
                if cursor=="next":
                    return {"feed":[]}
                return {"feed":[{"post":{
                    "uri":self.row["uri"],"cid":self.row["cid"],
                    "author":{"did":DID},
                    "record":self.row["value"]}}],"cursor":"next"}
            return super().json(url,body)
    api=Paginated()
    profile=archive.resolve("bluesky","qa-example.bsky.social",api)
    first,cursor=archive.page_records(profile,None,api)
    assert first and cursor.startswith("public-appview-v1:")
    final,end=archive.page_records(profile,cursor,api)
    assert final==[] and end is None
    assert api.feed_calls==2
