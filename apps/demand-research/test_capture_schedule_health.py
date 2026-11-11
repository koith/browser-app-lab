"""Synthetic schedule gap telemetry and bounded fresh-first catch-up QA."""
from datetime import datetime,timezone,timedelta
from pathlib import Path

import pytest
from capture_schedule_health import NAME,assess
import demand_capture_job as job
from test_degraded_encrypted_capture import (
    source,install_fake_media_fetch,private_synthetic_environment)
from test_demand_archive import FakeCloud


def event(run_id,at,*,name=NAME,event_name="schedule"):
    return {"id":run_id,"name":name,"event":event_name,
            "created_at":at.isoformat().replace("+00:00","Z")}


def test_near_five_minutes_is_measured_not_assumed():
    t=datetime(2026,11,3,12,30,tzinfo=timezone.utc)
    info=assess([event(99,t),event(98,t-timedelta(minutes=5))],
                current_id=99,current_time=t,event_name="schedule")
    assert info["status"]=="OBSERVED_NEAR_5M"
    assert info["observed_gap_minutes"]==5
    assert info["lookback_minutes"]==16


def test_missed_schedule_expands_bounded_catchup():
    t=datetime(2026,11,3,12,30,tzinfo=timezone.utc)
    info=assess([event(99,t),event(98,t-timedelta(minutes=137)),
                 event(97,t-timedelta(hours=4),name="UNRELATED")],
                current_id=99,current_time=t,event_name="schedule")
    assert info["status"]=="DELAYED_OR_MISSED"
    assert info["observed_gap_minutes"]==137
    assert info["lookback_minutes"]==153
    older=assess([event(98,t-timedelta(days=2))],
                 current_id=99,current_time=t,event_name="schedule")
    assert older["lookback_minutes"]==1440
    # The real scheduled capture showed a 273.8-minute gap: the previous
    # 180-minute cap missed a public window of ~94 minutes before this run.
    delayed=assess([event(98,t-timedelta(minutes=274))],
                   current_id=99,current_time=t,event_name="schedule")
    assert delayed["status"]=="DELAYED_OR_MISSED"
    assert delayed["lookback_minutes"]==290
    assert job.MAX_CATCHUP_MINUTES>=delayed["lookback_minutes"], "job must not silently re-cap the observed gap"
    assert delayed["lookback_minutes"]>=delayed["observed_gap_minutes"], (
        "the actually observed 274-minute delay must fit inside catch-up")
    # Actual 2026-11-11 scheduled gap was 461.9 minutes, but previous
    # 360m lookback silently omitted over 100m of eligible source time.
    actual=assess([event(98,t-timedelta(seconds=27714))],
                  current_id=99,current_time=t,event_name="schedule")
    assert actual["observed_gap_minutes"]==461.9
    assert actual["lookback_minutes"]==478
    assert actual["lookback_minutes"]>actual["observed_gap_minutes"]
    assert job.MAX_CATCHUP_MINUTES>=actual["lookback_minutes"]
    assert actual["lookback_minutes"]<=1440


def test_insufficient_evidence_never_labels_cron_healthy():
    t=datetime(2026,11,3,12,30,tzinfo=timezone.utc)
    only=assess([event(99,t)],current_id=99,current_time=t,event_name="schedule")
    assert only["status"]=="UNVERIFIED"
    assert only["previous_schedule_found"] is False
    not_scheduled=assess([event(99,t),event(98,t-timedelta(minutes=5))],
                         current_id=99,current_time=t,event_name="push")
    assert not_scheduled["status"]=="NOT_SCHEDULED"


def test_catchup_fetches_fresh_first_then_older_public_originals(tmp_path,monkeypatch):
    class Offline(FakeCloud):
        def preflight(self):
            raise RuntimeError("synthetic provider outage")
    install_fake_media_fetch(monkeypatch)
    monkeypatch.setenv("DEMAND_CAPTURE_LOOKBACK_MINUTES","80")
    now=1793667900
    starts=[]
    def getter(term,start,end):
        starts.append(start)
        if term!=job.TERMS[0]:
            return []
        if start>=now-16*60:
            return [source(210)]
        return [source(210),source(211)]
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[getter],cloud=Offline(),clock=lambda:now,
                run_id="123456940",fast_mode=True)
    query_count=len(job.TERMS)
    assert starts[:query_count]==[now-16*60]*query_count, (
        "every configured keyword must be searched in the fresh public window first")
    assert starts[query_count:]==[now-80*60]*query_count, (
        "the missed source window must be searched for every configured keyword")
    assert len(list(tmp_path.glob("*.enc")))==2, "exact same original not counted twice"


def test_capture_soft_budget_reports_partial_aes_before_external_timeout(
        tmp_path,monkeypatch,capsys):
    """A 1,080s hard TERM must not erase the aggregate or recovery evidence."""
    import json
    from test_degraded_encrypted_capture import (
        source,install_fake_media_fetch)
    class Offline(FakeCloud):
        def preflight(self):
            raise RuntimeError("synthetic remote outage")
    install_fake_media_fetch(monkeypatch)
    ticks=iter([0,1,800])
    rows=[source(310),source(311)]
    with pytest.raises(RuntimeError,match="unverified"):
        job.run(fetchers=[lambda term,start,end:rows if term==job.TERMS[0] else []],
                cloud=Offline(),clock=lambda:1793667900,run_id="123456949",
                fast_mode=True,elapsed_clock=lambda:next(ticks),max_fast_seconds=720)
    lines=capsys.readouterr().out.splitlines()
    marker="DEMAND_CAPTURE_AGGREGATE_ONLY "
    summaries=[json.loads(line[len(marker):]) for line in lines
               if line.startswith(marker)]
    assert len(summaries)==1,"aggregate must be printed before the hard TERM"
    result=summaries[0]
    assert result["soft_time_budget_exhausted"] is True
    assert result["budget_exhausted"] is True
    assert result["encrypted_recovery_files"]==1
    assert result["encrypted_only_originals"]==1
    assert result["saved_verified"]==0
    assert result["completeness_guaranteed"] is False
    assert len(list(tmp_path.glob("*.enc")))==1




def test_time_budget_with_no_cloud_failure_must_not_claim_capture_complete(
        monkeypatch,capsys):
    """A healthy backend cannot turn an entirely unscanned interval into PASS."""
    import json
    ticks=iter([0,800])
    with pytest.raises(RuntimeError,match="time budget exceeded"):
        job.run(fetchers=[lambda *_:[source(400)]],cloud=FakeCloud(),
                clock=lambda:1793667900,run_id="123456950",fast_mode=True,
                elapsed_clock=lambda:next(ticks),max_fast_seconds=720)
    prefix="DEMAND_CAPTURE_AGGREGATE_ONLY "
    out=[json.loads(line[len(prefix):]) for line in capsys.readouterr().out.splitlines()
         if line.startswith(prefix)]
    assert len(out)==1
    assert out[0]["soft_time_budget_exhausted"] is True
    assert out[0]["storage_failures"]==0
    assert out[0]["operational_status"]=="CAPTURE_TIME_BUDGET"
    assert out[0]["completeness_guaranteed"] is False
    assert out[0]["saved_verified"]==0




def test_queued_five_minute_capture_is_not_silently_replaced():
    """The queue preserves scheduled runs that GitHub did create.

    GitHub may still drop schedule events before job creation; never assert a
    strict five-minute SLA merely because YAML contains a cron expression.
    """
    workflow=(Path(__file__).resolve().parents[2]/
              ".github/workflows/demand-fast-capture.yml").read_text()
    concurrency=workflow.split("concurrency:",1)[1].split("\njobs:",1)[0]
    assert 'queue: max' in concurrency
    assert 'cancel-in-progress: false' in concurrency
    assert "pull_request" in concurrency and "production" in concurrency
    assert 'cron: "3-58/5 * * * *"' in workflow


def test_24_original_budget_rotates_fresh_public_provider_and_tag_priority():
    """A fixed first keyword previously starved later sources every 5 minutes."""
    fresh=("bluesky","mastodon","misskey","lemmy")
    old=tuple(x+"-catchup" for x in fresh)
    starts=[]
    for slot in range(len(fresh)*len(job.TERMS)):
        items=job.ordered_capture_batches(
            fresh+old,job.TERMS,slot*300,fresh_count=4,rotate=True)
        assert len(items)==len(fresh)*len(job.TERMS)*2
        # All live/fresh terms MUST precede older backfill queries.
        assert all(g in fresh for g,_ in items[:16])
        assert all(g in old for g,_ in items[16:])
        assert sorted((g,ts[0]) for g,ts in items[:16])==sorted(
            (g,t) for g in fresh for t in job.TERMS)
        starts.append((items[0][0],items[0][1][0]))
    assert len(set(starts))==16,"all four providers and four tags get a first slot"

    old_behavior=job.ordered_capture_batches(
        fresh,job.TERMS,1000,fresh_count=4,rotate=False)
    assert old_behavior[0]==("bluesky",(job.TERMS[0],))
    assert old_behavior[1]==("bluesky",(job.TERMS[1],))
