"""No secrets or network: durable one-click queue and safe readback fixtures."""
import hashlib
import pytest
import backup_queue


class FakeCloud:
    def __init__(self):
        self.items={}
        self.corrupt=False

    def write_immutable(self,key,data):
        if key in self.items and self.items[key]!=data:
            raise RuntimeError("immutable collision")
        self.items[key]=data
        return data

    def read_verified(self,key,expected_digest,*,cap):
        data=self.items.get(key)
        if self.corrupt:
            return b"damaged-content"
        return data if data and len(data)<=cap and hashlib.sha256(data).hexdigest()==expected_digest else None

    def read(self,key,*,cap,optional=False,domain=None):
        v=self.items.get(key)
        return v if v and len(v)<=cap else None

    def names(self,prefix):
        assert prefix==""
        return sorted(self.items)


def test_queued_account_remains_pending_until_ack(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    root=FakeCloud()
    job=backup_queue.create_request("bluesky","public-test.bsky.social",root)
    assert 1000000000<=job<=9999999999
    assert backup_queue.state(job,root)["accepted"] is None
    pending=backup_queue.pending(root)
    assert pending==[{"job_id":job,"platform":"bluesky",
                      "account":"public-test.bsky.social"}]
    accepted=backup_queue.accept(job,42199001234,root)
    assert accepted["workflow_run_id"]==42199001234
    assert backup_queue.pending(root)==[]
    assert backup_queue.state(job,root)["accepted"]["workflow_run_id"]==42199001234


def test_missing_and_damaged_remote_objects_never_count_as_queued(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    root=FakeCloud()
    assert backup_queue.state(1234567890,root) is None
    with pytest.raises(ValueError):
        backup_queue.create_request("invalid","public-test.bsky.social",root)
    with pytest.raises(ValueError):
        backup_queue.accept(1234567890,42199001234,root)
    job=backup_queue.create_request("bluesky","public-test.bsky.social",root)
    root.items["account-request-"+str(job)+".json"]=b"{}"
    with pytest.raises(RuntimeError):
        backup_queue.pending(root)


def test_failed_remote_sha_never_admits_a_backup_request(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    root=FakeCloud()
    root.corrupt=True
    with pytest.raises(RuntimeError,match="readback"):
        backup_queue.create_request("bluesky","public-test.bsky.social",root)


def test_queue_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DEMAND_ARCHIVE_QUEUE_MODE",raising=False)
    with pytest.raises(RuntimeError,match="disabled"):
        backup_queue.create_request("bluesky","public-test.bsky.social",FakeCloud())
