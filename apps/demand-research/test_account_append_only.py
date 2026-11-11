"""Synthetic append-only account archive integration tests (no live user data)."""
from types import SimpleNamespace
import pytest

from target_account_bundle import BundleStore, LayeredBundleCloud
from target_account_archive import run_one, resolve, archive_key
from verified_bundle_reader import MergedBundleAccountCloud
from test_target_account_archive import BlueAPI, blue_row
from demand_archive import post_key


def _capture(api, prior=()):
    store=BundleStore()
    root=LayeredBundleCloud(store,prior=prior)
    run_one("bluesky","qa-example.bsky.social",root=root,api=api,max_pages=1,
        archive_factory=lambda cloud,profile: LayeredBundleCloud(
          store,"account-archives/"+profile["platform"]+"/"+archive_key(profile)+"/",
          prior=prior))
    profile=resolve("bluesky","qa-example.bsky.social",api)
    account="bluesky-"+archive_key(profile)
    prefix="account-archives/bluesky/"+archive_key(profile)+"/"
    saved=SimpleNamespace(items=dict(store.objects),account=account,prefix=prefix,
                          recorded_at="2026-11-10T00:00:00+00:00")
    return saved


def test_edited_post_appends_version_and_preserves_first_original(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-unit-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    first=blue_row("edited01","original, remain unchanged")
    previous=_capture(BlueAPI({None:([first],None)}))
    pid=post_key("bluesky",first["uri"])
    first_bytes=previous.items[previous.prefix+"posts/"+pid+"/post.json"]
    edited=blue_row("edited01","modified content is a NEW immutable revision")
    next_delta=_capture(BlueAPI({None:([edited],None)}),(previous,))
    merged=MergedBundleAccountCloud([next_delta,previous])
    records=merged.load_catalog(include_entries=True)
    assert len(records)==2
    assert merged.read("posts/"+pid+"/post.json",cap=100_000)==first_bytes
    revisions=[p for p in records if p.get("revision_of")==pid]
    assert len(revisions)==1
    assert revisions[0]["text"]=="modified content is a NEW immutable revision"
    assert all(key not in next_delta.items for key in
               (previous.prefix+"posts/"+pid+"/post.json",
                previous.prefix+"metadata/source-records/"+pid+".json"))
    assert all(next_delta.items[k]==v for k,v in previous.items.items()
               if k in next_delta.items)  # no previously verified byte modified


def test_deleted_public_source_does_not_remove_saved_post(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-unit-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    previous=_capture(BlueAPI({None:([blue_row("vanish01","saved original")],None)}))
    delta=_capture(BlueAPI({None:([],None)}),(previous,))
    merged=MergedBundleAccountCloud([delta,previous])
    assert [p["text"] for p in merged.load_catalog()]==["saved original"]
    assert delta.items  # verified checkpoint even when provider now returns no posts


def test_unchanged_public_source_never_writes_duplicate_post(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-unit-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    source=blue_row("same001","unchanged public text")
    previous=_capture(BlueAPI({None:([source],None)}))
    delta=_capture(BlueAPI({None:([source],None)}),(previous,))
    assert not any(k.endswith("/post.json") for k in delta.items)
    assert len(MergedBundleAccountCloud([previous,delta]).load_catalog())==1


def test_scheduled_account_refresh_skips_missing_public_source(monkeypatch):
    """One deleted provider account cannot stall a still-public other account."""
    import target_account_bundle as bundle_job
    import github_temp_bundle
    from target_account_archive import SourceUnavailable

    def item(account, stamp):
        return SimpleNamespace(account=account,recorded_at=stamp,
            accounts={account:{"platform":"bluesky",
                               "profile_url":"https://bsky.app/profile/"+account}})
    first=item("bluesky-"+"a"*40,"2026-11-01T00:00:00Z")
    second=item("bluesky-"+"b"*40,"2026-11-02T00:00:00Z")
    monkeypatch.setattr(github_temp_bundle,"workflow_verified_bundles",
                        lambda max_scan: [second,first])
    attempts=[]
    def simulated(*,selected,prior_bundles):
        attempts.append(selected["account"])
        if len(attempts)==1:
            raise SourceUnavailable("synthetic provider HTTP 400")
        return {"remote_sha256_verified":True}
    monkeypatch.setattr(bundle_job,"execute_bundle",simulated)
    assert bundle_job.execute_scheduled()["remote_sha256_verified"] is True
    assert attempts==[first.accounts[first.account]["profile_url"],
                      second.accounts[second.account]["profile_url"]]


def test_scheduled_account_refresh_never_marks_all_missing_as_success(monkeypatch):
    import target_account_bundle as bundle_job
    import github_temp_bundle
    from target_account_archive import SourceUnavailable
    old="bluesky-"+"c"*40
    last=SimpleNamespace(account=old,recorded_at="2026-11-01T00:00:00Z",
         accounts={old:{"platform":"bluesky","profile_url":"https://bsky.app/profile/did:plc:synthetic"}})
    monkeypatch.setattr(github_temp_bundle,"workflow_verified_bundles",
                        lambda max_scan:[last])
    def denied(**kwargs):
        raise SourceUnavailable("synthetic public profile unavailable")
    monkeypatch.setattr(bundle_job,"execute_bundle",denied)
    with pytest.raises(SourceUnavailable,match="all registered"):
        bundle_job.execute_scheduled()


def test_latest_public_posts_are_captured_during_older_page_backfill(monkeypatch):
    """A saved historical pagination cursor must never hide newly posted text."""
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-unit-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    old=blue_row("old001","first page in prior run")
    earlier=blue_row("old000","older history in remaining cursor")
    new=blue_row("new001","newly posted while older history is incomplete")
    first=_capture(BlueAPI({None:([old],"older"),"older":([earlier],None)}))
    second=_capture(BlueAPI({None:([new,old],"older"),
                             "older":([earlier],None)}),(first,))
    merged=MergedBundleAccountCloud([first,second])
    posts=merged.load_catalog()
    assert {p["text"] for p in posts}=={
        "first page in prior run",
        "newly posted while older history is incomplete",
        "older history in remaining cursor",
    }
    assert second.items[first.prefix+"posts/"+post_key("bluesky",new["uri"])+"/post.json"]
    assert first.items[first.prefix+"posts/"+post_key("bluesky",old["uri"])+"/post.json"]
    assert not any(key in second.items for key in first.items
                   if key.endswith("/post.json"))


def test_modified_public_post_is_revised_during_older_page_backfill(monkeypatch):
    """An edited head post creates a separate immutable revision, not a replacement."""
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-unit-only")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    before=blue_row("same001","first immutable public text")
    older=blue_row("older001","historical original")
    after=blue_row("same001","newly edited public text")
    first=_capture(BlueAPI({None:([before],"next"),"next":([older],None)}))
    second=_capture(BlueAPI({None:([after],"next"),"next":([older],None)}),
                    (first,))
    merged=MergedBundleAccountCloud([second,first])
    records=merged.load_catalog()
    assert len(records)==3
    assert [p["text"] for p in records if p.get("revision_of")]==[
        "newly edited public text"]
    assert "first immutable public text" in {p["text"] for p in records}
    assert "historical original" in {p["text"] for p in records}
