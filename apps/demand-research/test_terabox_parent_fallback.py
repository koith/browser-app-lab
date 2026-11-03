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
        if (args[0]=="lsf" and "/posts" in args[1]
                and "--max-depth" in args):
            return b"" if "--terabox-domain" in args else None
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
            if (args[0]=="lsf" and "/posts" in args[1]
                    and "--max-depth" in args):
                return None
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


def test_safe_error_counters_pinpoint_missing_parent_or_upload():
    from demand_capture_job import public_error_class
    assert public_error_class(RuntimeError(
        "private cloud parent directory unverified"))=="backend_parent_unverified"
    assert public_error_class(RuntimeError(
        "private cloud mkdir failed (missing)"))=="backend_mkdir_missing"
    assert public_error_class(RuntimeError(
        "private cloud copyto failed (missing)"))=="backend_upload_missing"
    assert public_error_class(RuntimeError(
        "private cloud rcat failed (missing)"))=="backend_upload_missing"


def test_primary_missing_read_does_not_overwrite_verified_alternate_original():
    class StalePrimary(FakeCloud):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="cat" and "--terabox-domain" not in args:
                return None
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=StalePrimary()
    key="posts/"+"a"*40+"/capture.json"
    original=b"original synthetic archive bytes"
    cloud.objects[key]=original
    assert cloud.write_immutable(key,original) is False
    assert cloud.objects[key]==original
    with pytest.raises(RuntimeError,match="immutable archive key collision"):
        cloud.write_immutable(key,b"unrelated payload")
    assert cloud.objects[key]==original


def test_primary_upload_missing_and_parent_refresh_failure_uses_alt():
    class UploadMissing(FakeCloud):
        def __init__(self):
            super().__init__()
            self.primary_uploads=0
            self.alternate_uploads=0
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            primary="--terabox-domain" not in args
            if (args[0]=="mkdir" and primary and self.primary_uploads
                    and "/posts/" in args[1]):
                raise RuntimeError("private cloud mkdir failed (missing)")
            if (args[0]=="lsf" and primary and self.primary_uploads
                    and "/posts/" in args[1]):
                return None
            if args[0] in ("copyto","rcat") and primary:
                self.primary_uploads+=1
                raise RuntimeError("private cloud upload failed (missing)")
            if args[0]=="copyto" and not primary:
                self.alternate_uploads+=1
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=UploadMissing()
    p=post()
    cloud.save_post(p)
    assert cloud.primary_uploads>0
    assert cloud.alternate_uploads>0
    assert cloud.load_catalog()[0]["id"]==p["id"]
