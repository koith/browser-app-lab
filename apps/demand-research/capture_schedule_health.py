"""Read-only aggregate evidence for actual GitHub Actions fast-capture cadence.

Never log raw posts, archive paths, account identifiers, API credentials or
GitHub request stderr. No assertion of exact 5-minute execution from cron alone.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess

NAME = "INTERSECTION — Fast Private Public-Post Capture"
MIN_LOOKBACK = 16
MAX_LOOKBACK = 360


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assess(runs, *, current_id, current_time, event_name):
    result = {"status": "NOT_SCHEDULED", "observed_gap_minutes": None,
              "lookback_minutes": MIN_LOOKBACK, "previous_schedule_found": False}
    if event_name != "schedule":
        return result
    result["status"] = "UNVERIFIED"
    previous = []
    for item in runs:
        if (item.get("name") != NAME or item.get("event") != "schedule"
                or str(item.get("id", "")) == str(current_id)):
            continue
        try:
            t = parse_utc(item["created_at"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if t <= current_time:
            previous.append(t)
    if not previous:
        return result
    prior = max(previous)
    gap = max(0, (current_time - prior).total_seconds() / 60)
    rounded = round(gap, 1)
    result.update({"observed_gap_minutes": rounded,
                   "previous_schedule_found": True,
                   "status": "DELAYED_OR_MISSED" if gap > 8 else "OBSERVED_NEAR_5M",
                   "lookback_minutes": min(
                       MAX_LOOKBACK, max(MIN_LOOKBACK, math.ceil(gap) + MIN_LOOKBACK)
                   ) if gap > 8 else MIN_LOOKBACK})
    return result


def main():
    current=datetime.now(timezone.utc)
    event=os.getenv("GITHUB_EVENT_NAME", "")
    info={"status":"UNVERIFIED","lookback_minutes":MIN_LOOKBACK,
          "observed_gap_minutes":None,"previous_schedule_found":False}
    if event == "schedule":
        repo=os.getenv("GITHUB_REPOSITORY","")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
            try:
                api=subprocess.run(
                    ["gh","api",f"/repos/{repo}/actions/runs?event=schedule&per_page=100"],
                    capture_output=True,check=False,timeout=20)
                if api.returncode==0 and len(api.stdout)<3_000_000:
                    rows=json.loads(api.stdout).get("workflow_runs",[])
                    if isinstance(rows,list):
                        info=assess(rows,current_id=os.getenv("GITHUB_RUN_ID",""),
                                    current_time=current,event_name=event)
            except (OSError,ValueError,TypeError,subprocess.TimeoutExpired):
                pass
    else:
        info["status"]="NOT_SCHEDULED"
    destination=os.getenv("GITHUB_ENV","")
    if destination:
        with open(destination,"a",encoding="utf-8") as output:
            output.write("DEMAND_CAPTURE_LOOKBACK_MINUTES=" +
                         str(info["lookback_minutes"]) + "\n")
    print("INTERSECTION_CAPTURE_SCHEDULE_HEALTH",
          json.dumps(info,sort_keys=True),flush=True)


if __name__ == "__main__":
    main()
