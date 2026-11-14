"""No secrets or network: durable one-click queue and safe readback fixtures."""
import hashlib
import subprocess
import pytest
import backup_queue
from demand_archive import QueueStorageDenied


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


def test_two_pending_accounts_are_independent_and_acceptance_preserves_other(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    root=FakeCloud()
    old=backup_queue.create_request("bluesky","first.bsky.social",root)
    newer=backup_queue.create_request("mastodon","@second@mastodon.social",root)
    assert old!=newer
    pending=backup_queue.pending(root,limit=64)
    assert len(pending)==2
    assert {x["job_id"] for x in pending}=={old,newer}
    backup_queue.accept(old,42199000001,root)
    still=backup_queue.pending(root,limit=64)
    assert [x["job_id"] for x in still]==[newer]
    assert backup_queue.state(old,root)["accepted"]["workflow_run_id"]==42199000001
    assert backup_queue.state(newer,root)["accepted"] is None


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
    error_type = QueueStorageDenied if category == "authorization" else RuntimeError
    with pytest.raises(error_type):
        root.command(["cat", private, "--terabox-domain", "https://nephobox.com"])
    output = capsys.readouterr().out
    assert "operation=cat endpoint=alternate outcome=" + category + " elapsed_ms=" in output
    for sensitive in ("NDUS", "secret-cookie", "1234567890", "archive:", "nephobox.com"):
        assert sensitive not in output


def test_provider_denial_records_only_numeric_diagnostics(monkeypatch, capsys):
    stderr = br'HTTP error 403 (403 Forbidden) returned body: "{\"error_code\":31326,\"error_msg\":\"private-server-message cookie=secret-value\"}"'
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess(a[0], 1, b"", stderr))
    root = backup_queue.CloudArchive()
    root.trace_queue = True
    with pytest.raises(QueueStorageDenied) as raised:
        root.command(["cat", "archive:DemandResearch/account-request-1234567890.json"])
    output = capsys.readouterr().out
    assert "http_status=403" in output
    assert "provider_code=31326" in output
    assert "outcome=authorization" in output
    for sensitive in ("private-server-message", "secret-value", "cookie=", "1234567890", "archive:"):
        assert sensitive not in output + str(raised.value)


def test_first_readback_denial_stops_upload_and_endpoint_retries(monkeypatch, capsys):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE", "1")
    calls = []
    uploaded = False

    def run(args, **kwargs):
        nonlocal uploaded
        calls.append((args[0], "alternate" if "--terabox-domain" in args else "primary"))
        if args[0] == "cat":
            if not uploaded:
                return None
            raise RuntimeError("private cloud cat failed (authorization)")
        assert args[0] == "copyto"
        uploaded = True
        return b""

    root = backup_queue.CloudArchive(runner=run)
    with pytest.raises(QueueStorageDenied):
        backup_queue.create_request("bluesky", "public-test.bsky.social", root)
    assert calls == [("cat", "primary"), ("cat", "alternate"),
                     ("copyto", "primary"), ("cat", "primary")]
    assert uploaded
    output = capsys.readouterr().out
    assert "stage=write_immutable outcome=error" in output
    assert "stage=read_verified outcome=ok" not in output


def test_signed_url_words_do_not_turn_network_failure_into_access_denial(monkeypatch, capsys):
    stderr = (b'Failed to open: Get "https://download.example/file?cookie=secret403value": '
              b'connection reset by peer')
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess(a[0], 1, b"", stderr))
    root = backup_queue.CloudArchive()
    root.trace_queue = True
    with pytest.raises(RuntimeError, match="network_timeout"):
        root.command(["cat", "archive:DemandResearch/account-request-1234567890.json"])
    output = capsys.readouterr().out
    assert "outcome=network_timeout" in output
    assert "http_status=unknown" in output
    assert "secret403value" not in output and "download.example" not in output


def test_malformed_cookie_header_is_distinct_from_provider_denial(monkeypatch, capsys):
    stderr = b'net/http: invalid header field value for "Cookie": "secret-value"'
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
        subprocess.CompletedProcess(a[0], 1, b"", stderr))
    root = backup_queue.CloudArchive()
    root.trace_queue = True
    with pytest.raises(RuntimeError, match="invalid_header"):
        root.command(["cat", "archive:DemandResearch/account-request-1234567890.json"])
    output = capsys.readouterr().out
    assert "outcome=invalid_header" in output
    assert "http_status=unknown" in output
    assert "secret-value" not in output and "Cookie" not in output
