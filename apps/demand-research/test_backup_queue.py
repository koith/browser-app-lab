"""No secrets or network: durable one-click queue and safe readback fixtures."""
import hashlib
import subprocess
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


def test_queue_canonicalizes_short_usernames_without_url(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    cloud=FakeCloud()
    job_id=backup_queue.create_request("bluesky","@Public-Test",cloud)
    assert backup_queue.read_request(cloud,job_id)["account"]=="public-test.bsky.social"
    assert backup_queue.pending(cloud)==[
        {"job_id":job_id,"platform":"bluesky","account":"public-test.bsky.social"}]


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


@pytest.mark.parametrize("failed_stage", ["write_immutable", "read_verified"])
def test_queue_failure_trace_identifies_stage_without_private_payload(monkeypatch, capsys, failed_stage):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE", "1")
    monkeypatch.setattr(backup_queue.secrets, "randbelow", lambda _: 234567890)
    root = FakeCloud()
    private_error = "NDUS=secret-cookie account-request-1234567890.json private-account.bsky.social"

    def fail(*args, **kwargs):
        raise RuntimeError(private_error)

    monkeypatch.setattr(root, failed_stage, fail)
    with pytest.raises(RuntimeError, match="secret-cookie"):
        backup_queue.create_request("bluesky", "private-account.bsky.social", root)
    output = capsys.readouterr().out
    assert "stage=" + failed_stage + " outcome=error elapsed_ms=" in output
    assert "stage=read_verified outcome=ok" not in output
    for sensitive in ("NDUS", "secret-cookie", "1234567890", "private-account", ".json"):
        assert sensitive not in output


def test_remote_sha_failure_trace_never_reports_verified_success(monkeypatch, capsys):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE", "1")
    root = FakeCloud()
    root.corrupt = True
    with pytest.raises(RuntimeError, match="readback"):
        backup_queue.create_request("bluesky", "private-account.bsky.social", root)
    output = capsys.readouterr().out
    assert "stage=write_immutable outcome=ok" in output
    assert "stage=read_verified outcome=sha_unverified" in output
    assert "stage=read_verified outcome=ok" not in output
    assert "private-account" not in output


@pytest.mark.parametrize("category", ["authorization", "network_timeout", "process_timeout"])
def test_cloud_io_trace_classifies_failures_without_argv_or_exception(capsys, category):
    private = "NDUS=secret-cookie archive:DemandResearch/account-request-1234567890.json"

    def fail(args, **kwargs):
        if category == "process_timeout":
            raise RuntimeError(private) from subprocess.TimeoutExpired(["rclone", private], 120)
        raise RuntimeError(private + " (" + category + ")")

    root = backup_queue.CloudArchive(runner=fail)
    root.trace_queue = True
    with pytest.raises(RuntimeError):
        root.command(["cat", private, "--terabox-domain", "https://nephobox.com"])
    output = capsys.readouterr().out
    assert "operation=cat endpoint=alternate outcome=" + category + " elapsed_ms=" in output
    for sensitive in ("NDUS", "secret-cookie", "1234567890", "archive:", "nephobox.com"):
        assert sensitive not in output
