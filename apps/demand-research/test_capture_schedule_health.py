"""Synthetic schedule gap telemetry and bounded fresh-first catch-up QA."""
from datetime import datetime,timezone,timedelta

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
    assert older["lookback_minutes"]==360
    # The real scheduled capture showed a 273.8-minute gap: the previous
    # 180-minute cap missed a public window of ~94 minutes before this run.
    delayed=assess([event(98,t-timedelta(minutes=274))],
                   current_id=99,current_time=t,event_name="schedule")
    assert delayed["status"]=="DELAYED_OR_MISSED"
    assert delayed["lookback_minutes"]==290
    assert job.MAX_CATCHUP_MINUTES>=delayed["lookback_minutes"], "job must not silently re-cap the observed gap"
    assert delayed["lookback_minutes"]>=delayed["observed_gap_minutes"], (
        "the actually observed 274-minute delay must fit inside catch-up")


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
    assert starts[:3]==[now-16*60]*3, "recent public posts must be queried first"
    assert starts[3:]==[now-80*60]*3, "missing window is queried second"
    assert len(list(tmp_path.glob("*.enc")))==2, "exact same original not counted twice"
