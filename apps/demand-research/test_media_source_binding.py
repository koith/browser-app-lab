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
