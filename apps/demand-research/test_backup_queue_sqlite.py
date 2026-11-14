"""Offline one-click SQLite queue tests; no TeraBox read/write required."""
import pytest
import backup_queue


@pytest.fixture(autouse=True)
def configure(monkeypatch,tmp_path):
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_STORE","sqlite")
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_SQLITE",str(tmp_path/"queue.sqlite3"))


def test_selected_account_starts_without_any_cloud(monkeypatch):
    monkeypatch.setattr(backup_queue,"CloudArchive",lambda: (_ for _ in ()).throw(AssertionError("No TeraBox allowed")))
    job=backup_queue.create_request("bluesky","@public-test")
    assert 1000000000<=job<=9999999999
    assert backup_queue.pending()==[{"job_id":job,"platform":"bluesky",
                                   "account":"public-test.bsky.social"}]
    assert backup_queue.state(job)["accepted"] is None
    ack=backup_queue.accept(job,42340001000)
    assert ack["workflow_run_id"]==42340001000
    assert backup_queue.pending()==[]
    assert backup_queue.state(job)["accepted"]["workflow_run_id"]==42340001000
    with pytest.raises(ValueError):
        backup_queue.accept(job,42340001001)


def test_unknown_job_and_invalid_account_not_accepted():
    assert backup_queue.state(1234567890) is None
    with pytest.raises(ValueError):
        backup_queue.create_request("unsupported","example")
    with pytest.raises(ValueError):
        backup_queue.accept(1234567890,42340001000)


def test_queue_bounded_and_ordered():
    jobs=[backup_queue.create_request("bluesky",f"public-{i}.bsky.social")
          for i in range(backup_queue._MAX_OPEN)]
    assert {row["job_id"] for row in backup_queue.pending(limit=backup_queue._MAX_OPEN)}==set(jobs)
    with pytest.raises(RuntimeError,match="full"):
        backup_queue.create_request("bluesky","overflow.bsky.social")

def test_pending_never_silently_expires_after_seven_days(monkeypatch):
    import time
    old=backup_queue.create_request("bluesky","older-account.bsky.social")
    recent=backup_queue.create_request("mastodon","@newer@mastodon.social")
    with backup_queue._db() as conn:
        conn.execute("UPDATE account_requests SET created_at=? WHERE job_id=?",
                     (int(time.time())-9*86400,old))
    rows=backup_queue.pending(limit=4)
    assert [row["job_id"] for row in rows]==[old,recent]
    backup_queue.accept(old,42340000001)
    assert [row["job_id"] for row in backup_queue.pending(limit=4)]==[recent]


def test_overview_distinguishes_unprocessed_and_dispatched():
    first=backup_queue.create_request("bluesky","one.bsky.social")
    second=backup_queue.create_request("bluesky","two.bsky.social")
    assert backup_queue.overview()=={
        "known":True,"mode":"volatile_sqlite","queued":2,
        "dispatched":0,"total_requests":2}
    backup_queue.accept(first,42340000002)
    current=backup_queue.overview()
    assert current["queued"]==1
    assert current["dispatched"]==1
    assert current["total_requests"]==2
    assert second in [r["job_id"] for r in backup_queue.pending(limit=4)]


def test_accepted_workflows_are_available_for_bounded_auto_retry():
    old=backup_queue.create_request("bluesky","first.bsky.social")
    new=backup_queue.create_request("bluesky","second.bsky.social")
    backup_queue.accept(old,42410000001)
    backup_queue.accept(new,42410000002)
    assert set(backup_queue.accepted_runs(limit=4))=={42410000001,42410000002}


def test_bridge_autoretries_failed_workflow_without_creating_another_request(monkeypatch):
    import backup_bridge_poller as bridge
    import io
    import json
    monkeypatch.setenv("GITHUB_TOKEN","synthetic-ci-token")
    monkeypatch.setenv("GITHUB_RUN_NUMBER","0")
    monkeypatch.setattr(bridge,"oidc_assertion",lambda:"synthetic-oidc-assertion")
    def api(url,**kwargs):
        if url.endswith("/api/bridge/pending"):
            return {"requests":[]}
        if url.endswith("/api/bridge/accepted"):
            return {"runs":[42410000001]}
        raise AssertionError("unexpected bridge endpoint")
    monkeypatch.setattr(bridge,"request_json",api)
    actions=[]
    class Reply:
        def __init__(self,status,payload):
            self.status=status
            self.stream=io.BytesIO(json.dumps(payload).encode())
        def read(self,*args):
            return self.stream.read(*args)
        def __enter__(self):
            return self
        def __exit__(self,*args):
            return False
    def github(req,**kwargs):
        actions.append((req.get_method(),req.full_url))
        if req.get_method()=="GET":
            return Reply(200,{"id":42410000001,
                "path":".github/workflows/intersection-target-account-bundle.yml",
                "event":"workflow_dispatch","head_branch":"main",
                "status":"completed","conclusion":"failure","run_attempt":1})
        if req.get_method()=="POST" and req.full_url.endswith("/rerun-failed-jobs"):
            return Reply(201,{})
        raise AssertionError("unexpected GitHub request")
    monkeypatch.setattr(bridge,"urlopen",github)
    assert bridge.poll_once()=="NO_PENDING"
    assert len(actions)==2
    assert actions[-1][0]=="POST"
    assert actions[-1][1].endswith("/rerun-failed-jobs")
