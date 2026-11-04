"""Event-driven, fail-closed INTERSECTION GitHub Actions coordinator.

No clock, interval, age threshold, automatic checkbox, new ChatGPT thread, AI
billing, destructive cloud operation or unchecked auto-merge. A successful
workflow is only a *stage* signal, never proof of complete TeraBox recovery.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://api.github.com"
ISSUE = 607
TASKS = tuple(f"INT-{n:02d}" for n in range(1, 13))
CAPTURE = "demand-fast-capture.yml"
REPLAY = "demand-replay-encrypted.yml"
REPAIR = "demand-repair-archive.yml"
PAGES = "static.yml"
# Workflow name as surfaced by GitHub, not a guessed file path.
WORKFLOW_NAMES = {
    "INTERSECTION — Fast Private Public-Post Capture": CAPTURE,
    "INTERSECTION — Immediate Encrypted TeraBox Recovery": REPLAY,
    "INTERSECTION — Verify and Rebuild Private TeraBox Archive": REPAIR,
    "Deploy static content to Pages": PAGES,
    "INTERSECTION — Deployed Pages Desktop and Mobile QA": "intersection-deployed-pages-qa.yml",
    "Demand Research Public Source Probe": "demand-public-sources-probe.yml",
    "INTERSECTION Public Activity Ranking QA": "intersection-activity-ranking-qa.yml",
    "Demand Research — Instant Public Post Viewer Browser QA": "demand-live-browser.yml",
}
QA_FOR_TASK = {
    "INT-02": "demand-public-sources-probe.yml",
    "INT-04": REPAIR,
    "INT-07": "demand-live-browser.yml",
    "INT-08": "intersection-deployed-pages-qa.yml",
    "INT-09": "demand-public-sources-probe.yml",
    "INT-10": "intersection-activity-ranking-qa.yml",
}
WEB_TASKS = {"INT-07", "INT-08", "INT-10"}
DEPLOYED_QA = "intersection-deployed-pages-qa.yml"
ACTIVE = {"queued", "pending", "in_progress", "waiting", "requested"}
# Explicitly allowlisted dispatches. No arbitrary user-provided workflow path.
DISPATCHABLE = frozenset(QA_FOR_TASK.values()) | {REPAIR, DEPLOYED_QA}


def first_incomplete(body):
    found = {}
    for line in (body or "").splitlines():
        m = re.match(r"^- \[([ xX])\] \*\*(INT-\d{2})\*\*(?:\s|$)", line)
        if m and m.group(2) in TASKS and m.group(2) not in found:
            found[m.group(2)] = m.group(1).lower() == "x"
    for t in TASKS:
        if t not in found:
            return t, "MISSING_FROM_ISSUE"
        if not found[t]:
            return t, "OPEN"
    return None, "ALL_CHECKED_UNVERIFIED"


def trustworthy_event(event_name, payload, repo):
    """Never grant main-branch Actions write token to a fork/PR event."""
    if event_name == "workflow_run":
        run = payload.get("workflow_run") or {}
        source = run.get("head_repository") or {}
        if (run.get("status") != "completed" or run.get("head_branch") != "main"
                or run.get("event") == "pull_request"
                or source.get("full_name") != repo
                or run.get("name") not in WORKFLOW_NAMES
                or not isinstance(run.get("id"), int)):
            return False
        return True
    if event_name == "issues":
        issue = payload.get("issue") or {}
        return (issue.get("number") == ISSUE
                and payload.get("action") in ("edited", "reopened")
                and not issue.get("pull_request"))
    if event_name == "push":
        return payload.get("ref") == "refs/heads/main" and (
            (payload.get("repository") or {}).get("full_name") == repo
        )
    return event_name == "workflow_dispatch"


def latest_on_sha(runs, sha):
    return next((r for r in runs
                 if r.get("head_sha") == sha and r.get("event") != "pull_request"),
                None)


def safe_status(run):
    if run is None:
        return "MISSING"
    state = run.get("status")
    if state in ACTIVE:
        return "ACTIVE"
    if state == "completed":
        if run.get("conclusion") == "success":
            return "PASS"
        return "FAILED_OR_UNVERIFIED"
    return "UNVERIFIED"


def action(task, verb, reason, workflow=None):
    return {"task": task, "action": verb, "reason": reason,
            "workflow": workflow}


def decide(task, trigger, main_sha, runs):
    """Only respond to proven events; no sleep/cooldown/timer arithmetic.

    A task advances only when issue #607 has a verified [x] checkbox.
    UI tasks must independently pass QA, Pages deployment and live browser QA.
    """
    if task is None:
        return action(task, "NONE", "NO_OPEN_TASK_VERIFIED")
    if task == "INT-01":
        if trigger.get("name") == "INTERSECTION — Immediate Encrypted TeraBox Recovery":
            if trigger.get("conclusion") != "success":
                return action(task, "NONE", "RECOVERY_FAILED_REQUIRES_CODE_REPAIR")
            repair_runs = runs.get(REPAIR, [])
            if any(safe_status(x) == "ACTIVE" for x in repair_runs):
                return action(task, "NONE", "REPAIR_ALREADY_IN_PROGRESS")
            # A later repair attempt, even if it failed, is evidence that this
            # recovery event was already processed. Never spin on a failure.
            if any(x.get("id", 0) > trigger.get("id", 0)
                   for x in repair_runs):
                return action(task, "NONE", "REPAIR_ALREADY_ATTEMPTED_AFTER_REPLAY")
            return action(task, "DISPATCH", "RECOVERY_COMPLETE_START_REMOTE_RECONCILIATION",
                          REPAIR)
        if trigger.get("name") == "INTERSECTION — Verify and Rebuild Private TeraBox Archive":
            if trigger.get("conclusion") == "success":
                return action(task, "NONE", "REBUILD_PASS_FULL_HISTORICAL_GATE_STILL_UNVERIFIED")
            return action(task, "NONE", "REBUILD_FAILED_REQUIRES_CODE_REPAIR")
        if trigger.get("name") == "INTERSECTION — Fast Private Public-Post Capture":
            return action(task, "NONE",
                          "CAPTURE_COMPLETED_NATIVE_REPLAY_HANDLES_FAILED_RUNS")
        return action(task, "NONE", "INT01_OPERATIONAL_PROOF_PENDING")

    qa = QA_FOR_TASK.get(task)
    if not qa:
        return action(task, "NONE", "NO_TRUSTED_TASK_QA_IMPLEMENTED")
    qa_runs = runs.get(qa, [])
    if any(safe_status(r) == "ACTIVE" for r in qa_runs):
        return action(task, "NONE", "TASK_QA_IN_PROGRESS")
    matched = latest_on_sha(qa_runs, main_sha)
    state = safe_status(matched)
    if state == "MISSING":
        return action(task, "DISPATCH", "VERIFIED_PREDECESSOR_START_TASK_QA", qa)
    if state == "FAILED_OR_UNVERIFIED":
        return action(task, "NONE", "QA_FAILED_FIX_CODE_BEFORE_RERUN")
    if state != "PASS":
        return action(task, "NONE", "TASK_QA_NOT_YET_VERIFIED")
    if task not in WEB_TASKS:
        return action(task, "NONE", "TASK_QA_PASS_PRODUCT_ACCEPTANCE_STILL_REQUIRED")
    deploy = latest_on_sha(runs.get(PAGES, []), main_sha)
    if safe_status(deploy) != "PASS":
        return action(task, "NONE", "WAIT_FOR_PAGES_DEPLOY_ON_SAME_COMMIT")
    if qa == DEPLOYED_QA:
        return action(task, "NONE", "DEPLOYED_BROWSER_QA_PASS_FINAL_PRODUCT_GATE_PENDING")
    live_rows = runs.get(DEPLOYED_QA, [])
    if any(safe_status(r) == "ACTIVE" for r in live_rows):
        return action(task, "NONE", "DEPLOYED_BROWSER_QA_IN_PROGRESS")
    live = latest_on_sha(live_rows, main_sha)
    if safe_status(live) == "MISSING":
        return action(task, "DISPATCH", "PAGES_PASS_START_DEPLOYED_BROWSER_QA",
                      DEPLOYED_QA)
    if safe_status(live) == "PASS":
        return action(task, "NONE", "DEPLOYED_QA_PASS_FINAL_PRODUCT_GATE_PENDING")
    return action(task, "NONE", "DEPLOYED_QA_FAILED_REQUIRES_CODE_FIX")


class GitHub:
    def __init__(self, repo, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("invalid repository")
        if not token:
            raise ValueError("missing Github Actions token")
        self.repo = repo
        self.token = token

    def request(self, path, *, method="GET", data=None):
        if not path.startswith("/"):
            raise ValueError("invalid API")
        body = json.dumps(data).encode() if data is not None else None
        request = Request(
            API + path, method=method, data=body,
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "User-Agent": "intersection-zero-cost-event-pipeline"},
        )
        with urlopen(request, timeout=25) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("GitHub API response exceeds bound")
            return json.loads(raw) if raw else {}

    def workflow_runs(self, workflow):
        if workflow not in DISPATCHABLE | {CAPTURE, REPLAY, PAGES}:
            raise ValueError("unapproved workflow")
        base = f"/repos/{self.repo}/actions/workflows/{workflow}/runs"
        info = self.request(base + "?branch=main&per_page=100")
        rows = info.get("workflow_runs", [])
        if not isinstance(rows, list):
            raise ValueError("invalid workflow run list")
        # Old queued runs may not be in first page; check independently.
        unique = {x["id"]: x for x in rows if isinstance(x, dict)
                  and isinstance(x.get("id"), int)}
        for state in sorted(ACTIVE):
            active = self.request(base + f"?branch=main&status={state}&per_page=100")
            if active.get("total_count", 0) > 100:
                raise ValueError("ambiguous active workflow queue")
            for x in active.get("workflow_runs", []):
                if isinstance(x, dict) and isinstance(x.get("id"), int):
                    unique[x["id"]] = x
        return sorted(unique.values(), key=lambda x: x["id"], reverse=True)

    def dispatch(self, workflow):
        if workflow not in DISPATCHABLE:
            raise ValueError("unapproved dispatch")
        self.request(f"/repos/{self.repo}/actions/workflows/{workflow}/dispatches",
                     method="POST", data={"ref": "main"})


def main():
    repo = os.getenv("GITHUB_REPOSITORY", "")
    gh = GitHub(repo, os.getenv("GH_TOKEN", ""))
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    event_path = os.getenv("GITHUB_EVENT_PATH", "")
    # GitHub-generated event payload, not repository or untrusted PR source.
    data = json.loads(Path(event_path).read_text(encoding="utf-8")) if event_path else {}
    if not trustworthy_event(event_name, data, repo):
        print("INTERSECTION_EVENT_PIPELINE",
              json.dumps(action(None, "NONE", "UNTRUSTED_OR_UNRELATED_EVENT")))
        return
    issue = gh.request(f"/repos/{repo}/issues/{ISSUE}")
    task, state = first_incomplete(issue.get("body") or "")
    if state == "MISSING_FROM_ISSUE":
        result = action(task, "NONE", "ISSUE_TASK_CHECKBOX_MISSING_FAIL_CLOSED")
    else:
        commit = gh.request(f"/repos/{repo}/commits/main")
        sha = commit.get("sha", "")
        if not re.fullmatch("[0-9a-f]{40}", sha):
            raise ValueError("current main commit unverifiable")
        trigger = (data.get("workflow_run") or {}
                   if event_name == "workflow_run" else {})
        want = ([REPAIR] if task == "INT-01" and
                trigger.get("name") == "INTERSECTION — Immediate Encrypted TeraBox Recovery"
                else [QA_FOR_TASK[task], PAGES, DEPLOYED_QA]
                if task in QA_FOR_TASK and task in WEB_TASKS
                else [QA_FOR_TASK[task]]
                if task in QA_FOR_TASK else [])
        runs = {w: gh.workflow_runs(w) for w in set(want)}
        result = decide(task, trigger, sha, runs)
        if result["action"] == "DISPATCH":
            gh.dispatch(result["workflow"])
            result["action"] = "STAGE_DISPATCHED"
    # Emit only allowlisted workflow IDs, task codes, stage reasons; no raw
    # source data, cloud filenames, cookies, encryption keys or post content.
    print("INTERSECTION_EVENT_PIPELINE", json.dumps(result, sort_keys=True))
    with open(os.getenv("GITHUB_STEP_SUMMARY", "/dev/null"), "a", encoding="utf-8") as f:
        f.write("## INTERSECTION event-driven progression\n\n"
                f"Task: {result['task']}, action: {result['action']}, "
                f"reason: {result['reason']}\n\n"
                "An Actions stage passing never implies archive completion.\n")


if __name__ == "__main__":
    main()
