"""Bounded verified append-only continuation of public account ZIPs."""
import io
import json

import pytest
import target_account_bundle as worker


@pytest.fixture
def trusted(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY","koith/browser-app-lab")
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME","workflow_dispatch")
    monkeypatch.setenv("GITHUB_TOKEN","synthetic-nonsecret-test-token-of-sufficient-length")
    monkeypatch.setenv("TARGET_PLATFORM","bluesky")
    monkeypatch.setenv("TARGET_ACCOUNT","qa-example.bsky.social")
    monkeypatch.setenv("TARGET_RESUME_PASS","2")


def proof(**updates):
    return {"remote_sha256_verified":True,
            "source_partial":True,
            "source_interruption":"STAGING_LIMIT",
            "public_posts_in_bundle":8,**updates}


def test_exact_proved_staging_limit_dispatches_next_immutable_pass(trusted):
    sent=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):return json.dumps(
            {"workflow_run_id":44653123456}).encode()
    def fake_send(request,timeout):
        sent.append((request,timeout))
        return Response()
    outcome=worker.dispatch_verified_followup(proof(),send=fake_send)
    assert outcome=="DISPATCHED"
    assert len(sent)==1
    request,timeout=sent[0]
    assert timeout==30 and request.get_method()=="POST"
    payload=json.loads(request.data)
    assert payload["ref"]=="main"
    assert payload["return_run_details"] is True
    assert payload["inputs"]=={"platform":"bluesky",
        "account":"qa-example.bsky.social","max_pages":"all",
        "resume_pass":"3"}


@pytest.mark.parametrize("unverified",[
    {"remote_sha256_verified":False},
    {"source_partial":False},
    {"source_interruption":"OTHER"},
    {"source_interruption":None},
    {"public_posts_in_bundle":0},
])
def test_never_dispatch_for_unproved_or_non_progressing_source(trusted,unverified):
    def must_not_dispatch(*args,**kwargs):
        raise AssertionError("Bad auto dispatch")
    assert worker.dispatch_verified_followup(
        proof(**unverified),send=must_not_dispatch)=="NOT_ELIGIBLE"


def test_bounded_pass_cap_disallows_infinite_autoretry(trusted,monkeypatch):
    monkeypatch.setenv("TARGET_RESUME_PASS",
                       str(worker.MAX_AUTOMATED_CONTINUATION_PASSES))
    assert worker.dispatch_verified_followup(proof())=="LIMIT_REACHED"
    monkeypatch.setenv("TARGET_RESUME_PASS","9999")
    with pytest.raises(RuntimeError,match="Invalid bounded"):
        worker.dispatch_verified_followup(proof())


def test_untrusted_fork_or_scheduled_context_cannot_dispatch(trusted,monkeypatch):
    monkeypatch.setenv("GITHUB_REF","refs/pull/123/merge")
    assert worker.dispatch_verified_followup(proof())=="NOT_TRUSTED_CONTEXT"
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME","schedule")
    assert worker.dispatch_verified_followup(proof())=="NOT_TRUSTED_CONTEXT"


def test_authenticated_dispatch_needs_exact_run_id_readback(trusted):
    class NoRun:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,limit):return b'{"workflow_run_id":null}'
    with pytest.raises(RuntimeError,match="trackable"):
        worker.dispatch_verified_followup(proof(),send=lambda *_args,**_kw:NoRun())
