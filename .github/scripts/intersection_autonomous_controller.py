"""Bounded GitHub-native INTERSECTION controller (no external AI, no secrets).

Selects the first incomplete issue task and safely dispatches an existing,
already-tested recovery workflow only when it is not running or queued and a
recent capture has failed. Never mutates TeraBox, marks an issue complete,
creates a chat, or merges a code change. This is a deterministic first stage,
not a claim of autonomous AI code development.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://api.github.com"
ISSUE = 607
RECOVERY = "demand-replay-encrypted.yml"
CAPTURE = "demand-fast-capture.yml"
TASKS = tuple(f"INT-{i:02d}" for i in range(1, 13))
COOLDOWN = timedelta(hours=6)
RECENT_CAPTURE = timedelta(hours=6)
ACTIVE = {"queued", "pending", "in_progress", "waiting", "requested"}


def parse_tasks(body):
    """Only top-level task checkboxes; historical subtask notes don't count."""
    found = {}
    for line in body.splitlines():
        match = re.match(r"^- \[([ xX])\] \*\*(INT-\d{2})\*\*(?:\s|$)", line)
        if match and match.group(2) in TASKS and match.group(2) not in found:
            found[match.group(2)] = match.group(1).lower() == "x"
    return found


def first_incomplete(body):
    tasks = parse_tasks(body)
    for task in TASKS:
        if task not in tasks:
            # Missing items cannot silently be treated as completed.
            return task, "MISSING_FROM_ISSUE"
        if not tasks[task]:
            return task, "OPEN"
    return None, "ALL_CHECKED_UNVERIFIED"


def parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def decide(issue_body, captures, replays, now):
    """Fail closed: no duplicate replay; no cross-task promotion."""
    task, reason = first_incomplete(issue_body)
    base = {"task": task, "task_state": reason, "action": "NONE",
            "reason": "NO_VERIFIED_GATE", "source_run_id": None}
    if task != "INT-01":
        base["reason"] = "NEXT_TASK_REQUIRES_ITS_OWN_VERIFIED_ACCEPTANCE_GATE"
        return base
    if any(row.get("status") in ACTIVE for row in replays):
        base["reason"] = "RECOVERY_ALREADY_QUEUED_OR_RUNNING"
        return base
    if any(row.get("status") not in ACTIVE | {"completed"} for row in replays):
        base["reason"] = "RECOVERY_STATUS_UNVERIFIED"
        return base
    if not captures:
        base["reason"] = "CAPTURE_EVIDENCE_MISSING"
        return base
    latest = captures[0]
    when = parse_date(latest.get("created_at"))
    if when is None or when > now or now - when > RECENT_CAPTURE:
        base["reason"] = "NO_RECENT_CAPTURE_EVIDENCE"
        return base
    if latest.get("status") != "completed":
        base["reason"] = "CAPTURE_STILL_RUNNING_OR_QUEUED"
        return base
    if latest.get("conclusion") != "failure":
        base["reason"] = "NO_RECENT_FAILED_CAPTURE"
        return base
    source_id = latest.get("id")
    if not isinstance(source_id, int) or source_id < 1:
        base["reason"] = "INVALID_SOURCE_RUN_ID"
        return base
    for row in replays:
        started = parse_date(row.get("created_at"))
        if started is None:
            base["reason"] = "RECOVERY_TIMESTAMP_UNVERIFIED"
            return base
        if started > now or now - started < COOLDOWN:
            base["reason"] = "RECOVERY_COOLDOWN"
            return base
    base.update({"action": "DISPATCH_RECOVERY",
                 "reason": "RECENT_FAILED_CAPTURE_NO_RECOVERY_IN_FLIGHT",
                 "source_run_id": source_id})
    return base


class GitHub:
    def __init__(self, repo, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("invalid repo")
        if not token:
            raise ValueError("missing Actions token")
        self.repo = repo
        self.token = token

    def request(self, path, *, method="GET", data=None):
        if not path.startswith("/"):
            raise ValueError("invalid API path")
        req = Request(
            API + path,
            data=json.dumps(data).encode("utf-8") if data is not None else None,
            method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "intersection-autonomous-controller",
            },
        )
        with urlopen(req, timeout=25) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("oversized API response")
            return json.loads(raw) if raw else {}

    def runs(self, workflow):
        # 100 includes all currently queued replay runs; fail closed if
        # GitHub truncates a larger backlog rather than dispatching duplicates.
        result = self.request(
            f"/repos/{self.repo}/actions/workflows/{workflow}/runs"
            "?branch=main&per_page=100"
        )
        if result.get("total_count", 0) > 100:
            raise ValueError("workflow run history truncated; refuse dispatch")
        runs = result.get("workflow_runs", [])
        if not isinstance(runs, list):
            raise ValueError("invalid run response")
        return runs

    def dispatch_replay(self, source_id):
        return self.request(
            f"/repos/{self.repo}/actions/workflows/{RECOVERY}/dispatches",
            method="POST",
            data={"ref": "main", "inputs": {"source_run_id": str(source_id)}},
        )


def main():
    gh = GitHub(os.getenv("GITHUB_REPOSITORY", ""),
                os.getenv("GH_TOKEN", ""))
    issue = gh.request(f"/repos/{gh.repo}/issues/{ISSUE}")
    captures = gh.runs(CAPTURE)
    replays = gh.runs(RECOVERY)
    decision = decide(
        issue.get("body") or "", captures, replays,
        datetime.now(timezone.utc),
    )
    # No private source text, credentials, archive paths or raw API errors.
    if decision["action"] == "DISPATCH_RECOVERY":
        gh.dispatch_replay(decision["source_run_id"])
        decision["action"] = "RECOVERY_DISPATCHED"
    print("INTERSECTION_AUTONOMOUS_CONTROLLER",
          json.dumps(decision, sort_keys=True), flush=True)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(
                "## INTERSECTION safe controller\n\n"
                f"Priority: {decision['task'] or 'NONE'}; "
                f"action: {decision['action']}; "
                f"reason: {decision['reason']}\n\n"
                "Never claim completion without verified original and media SHA.\n"
            )


if __name__ == "__main__":
    main()
