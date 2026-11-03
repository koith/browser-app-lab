"""Isolated regression checks for TeraBox nested-path failures.

Only synthetic bytes; never reads credentials or a live account.
"""
import pytest

from test_demand_archive import FakeCloud, post


@pytest.fixture(autouse=True)
def no_remote_backoff_in_synthetic_test(monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep", lambda _: None)


class PrimaryParentMissing(FakeCloud):
    def __init__(self):
        super().__init__()
        self.primary_mkdir_errors = 0
        self.alternate_mkdirs = 0

    def fake(self,args,data=None,timeout=150,allow_missing=False):
        if args[0]=="mkdir" and "/posts" in args[1]:
            if "--terabox-domain" not in args:
                self.primary_mkdir_errors += 1
                raise RuntimeError("private cloud mkdir failed (missing)")
            self.alternate_mkdirs += 1
        return super().fake(args,data=data,timeout=timeout,
                            allow_missing=allow_missing)


def test_primary_folder_failure_uses_alternate_before_upload():
    cloud=PrimaryParentMissing()
    p=post()
    cloud.save_post(p)
    assert cloud.primary_mkdir_errors>0
    assert cloud.alternate_mkdirs>0
    assert cloud.load_catalog()[0]["id"]==p["id"]
    assert "posts/"+p["id"]+"/post.json" in cloud.objects


def test_alternate_folder_failure_does_not_claim_archive_saved():
    class BothParentsMissing(PrimaryParentMissing):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="mkdir" and "/posts" in args[1]:
                raise RuntimeError("private cloud mkdir failed (missing)")
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=BothParentsMissing()
    with pytest.raises(RuntimeError,match="parent directory unverified"):
        cloud.save_post(post())
    assert not any(k.endswith("/post.json") for k in cloud.objects)


def test_missing_account_access_is_not_bypassed_with_alternate_domain():
    class Denied(PrimaryParentMissing):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="mkdir" and "/posts" in args[1]:
                raise RuntimeError("private cloud mkdir failed (authorization)")
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=Denied()
    with pytest.raises(RuntimeError,match="authorization"):
        cloud.save_post(post())
    assert cloud.alternate_mkdirs==0
    assert cloud.objects=={}
