"""Synthetic checks that a stale TeraBox catalog listing is retried safely."""
import pytest
from test_demand_archive import FakeCloud, post
from rebuild_archive import rebuild


@pytest.fixture(autouse=True)
def fast_rechecks(monkeypatch):
    monkeypatch.setattr("rebuild_archive.time.sleep",lambda _:None)
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic")
    monkeypatch.setenv("DEMAND_CAPTURE_PUBLIC_ALLOWED","1")


class DelayedManifestListing(FakeCloud):
    def __init__(self,stale_reads=1):
        super().__init__()
        self.stale_reads=stale_reads
        self.observed_stale=0

    def fake(self,args,data=None,timeout=150,allow_missing=False):
        if (args[0]=="lsf" and "/metadata/manifests" in args[1]
                and "--files-only" in args
                and any(k.startswith("metadata/manifests/manifest-")
                        for k in self.objects)
                and self.observed_stale<self.stale_reads):
            self.observed_stale+=1
            return b""
        return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)


def test_fresh_reader_retries_one_stale_manifest_without_false_catalog_corruption():
    cloud=DelayedManifestListing(stale_reads=1)
    cloud.save_post(post())
    result=rebuild(cloud=cloud,run_id="123456991")
    assert cloud.observed_stale==1
    assert result["independent_read_attempts"]>=2
    assert result["snapshot_sha_verified"] is True
    assert result["fully_reconciled"] is True
    assert result["published_catalog_posts"]==1
    assert result["journal_readable_posts"]==1


def test_permanently_unlisted_catalog_does_not_get_marked_verified():
    cloud=DelayedManifestListing(stale_reads=99)
    cloud.save_post(post())
    with pytest.raises(RuntimeError,match="unverified or missing"):
        rebuild(cloud=cloud,run_id="123456992")
    # Each independent pass reads the snapshot and journal separately.
    assert cloud.observed_stale>=4
    assert "posts/"+post()["id"]+"/post.json" in cloud.objects
    assert "metadata/manifests/manifest-123456992.json" in cloud.objects
