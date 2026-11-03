"""Isolated checks for safe selection of private encrypted recovery artifacts."""
import json
import pytest
import recover_spool_artifacts as replay


@pytest.fixture(autouse=True)
def repo_context(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY","koith/browser-app-lab")


def _artifact(run_id,branch="main",head_repo=1284121913,origin_repo=1284121913):
    return {"name":"intersection-private-recovery",
            "created_at":"2026-11-03T11:54:57Z","expired":False,
            "size_in_bytes":3600,
            "workflow_run":{"id":run_id,"repository_id":origin_repo,
                            "head_repository_id":head_repo,"head_branch":branch}}


def test_backlog_lists_only_trusted_main_branch_artifacts(monkeypatch):
    page={"artifacts":[
        _artifact(41629506950),
        _artifact(41628500000,branch="feature/untrusted-pr"),
        _artifact(41628500001,head_repo=7),
        {**_artifact(41628500002),"expired":True},
        {**_artifact(41628500003),"size_in_bytes":250_000_000},
    ]}
    calls=[]
    def fake_gh(args,**kwargs):
        calls.append(args)
        return json.dumps(page).encode()
    monkeypatch.setattr(replay,"_gh",fake_gh)
    assert replay.list_candidates()==[
        ("2026-11-03T11:54:57Z",41629506950,"intersection-private-recovery")]
    assert len(calls)==1


@pytest.mark.parametrize("changed",[
    {"head_branch":"feature/untrusted"},
    {"event":"pull_request"},
    {"name":"Some Untrusted Other Workflow"},
    {"head_repository":{"full_name":"untrusted/fork"}},
])
def test_targeted_replay_rejects_untrusted_source_run(monkeypatch,changed):
    approved={"name":"INTERSECTION — Fast Private Public-Post Capture",
              "head_branch":"main","event":"push",
              "head_repository":{"full_name":"koith/browser-app-lab"}}
    approved.update(changed)
    monkeypatch.setattr(replay,"_gh",
                        lambda args,**kwargs:json.dumps(approved).encode())
    with pytest.raises(RuntimeError,match="untrusted"):
        replay.validate_source_run("41629506950")


def test_targeted_replay_accepts_trusted_main_capture(monkeypatch):
    approved={"name":"INTERSECTION — Fast Private Public-Post Capture",
              "head_branch":"main","event":"push",
              "head_repository":{"full_name":"koith/browser-app-lab"}}
    monkeypatch.setattr(replay,"_gh",
                        lambda args,**kwargs:json.dumps(approved).encode())
    assert replay.validate_source_run("41629506950") is None
