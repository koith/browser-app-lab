#!/usr/bin/env python3
"""Build the small 4LEAF state index from GitHub Issues; never load legacy history."""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ISSUE_TITLE = re.compile(r"^\[4LEAF\]\[([A-Za-z0-9-]+)\]\s+(.+)$")
PRIORITY = re.compile(r"(?:우선순위)[^\n]{0,25}?(P[0-9]+)")
LEGACY_TODO = re.compile(r"원장 상태[^\n]{0,30}todo")
LEGACY_DONE = re.compile(r"(?:이관 원장 상태|기존 상태)[^\n]{0,30}done")
ACCEPTED_MARKER = "<!-- 4LEAF-ACCEPTED-WITH-EVIDENCE -->"
OUTPUT = Path("apps/4leaf/rog/docs/RESTORATION_STATUS.json")
HANDOFF = Path("apps/4leaf/rog/docs/CHAT_HANDOFF_BRIEF.json")
FOCUS = Path("apps/4leaf/rog/docs/DELIVERY_FOCUS.json")


def classify(issue):
    body = issue.get("body") or ""
    if issue["state"] == "closed":
        if LEGACY_DONE.search(body):
            return "done", "legacy-import"
        if ACCEPTED_MARKER in body and re.search(r"https://\S+", body):
            return "done", "accepted-with-evidence"
        return "review_required", "closed-without-acceptance"
    if LEGACY_TODO.search(body):
        return "todo", "not-started"
    return "in_progress", "open"


def convert(items, previous=None):
    tasks = []
    seen = set()
    for issue in items:
        if "pull_request" in issue:
            continue
        m = ISSUE_TITLE.match(issue.get("title") or "")
        if not m:
            continue
        task_id, title = m.groups()
        if task_id in seen:
            raise ValueError("duplicate 4LEAF task ID: " + task_id)
        seen.add(task_id)
        status, evidence = classify(issue)
        pm = PRIORITY.search(issue.get("body") or "")
        tasks.append({
            "id": task_id,
            "issue": issue["number"],
            "title": title,
            "priority": pm.group(1) if pm else "unassigned",
            "status": status,
            "acceptance": evidence,
            "url": issue["html_url"],
        })
    if not tasks:
        raise ValueError("no 4LEAF Issues matched; refusing to overwrite index")
    tasks.sort(key=lambda t: t["id"])
    if previous:
        before = {t["id"] for t in previous.get("tasks", [])}
        missing = sorted(before - seen)
        if missing:
            raise ValueError("existing task IDs disappeared: " + ", ".join(missing))
    counts = {name: sum(t["status"] == name for t in tasks)
              for name in ("done", "in_progress", "todo", "review_required")}
    return {
        "schemaVersion": 2,
        "sourceOfTruth": "GitHub Issues with [4LEAF][ID] title",
        "legacyEvidence": "apps/4leaf/rog/docs/RESTORATION_LEDGER.json",
        "counts": {"total": len(tasks), **counts,
                   "remaining": len(tasks) - counts["done"]},
        "tasks": tasks,
    }


def make_handoff(status, focus):
    """Minimal, deterministic fresh-chat state; never include legacy events."""
    current = [task for task in status["tasks"] if task["status"] != "done"]
    selected = focus.get("activeFocus")
    if selected not in {task["id"] for task in current}:
        raise ValueError("activeFocus missing from the actual open GitHub Issues")
    if len(current) != status["counts"]["remaining"]:
        raise ValueError("handoff counts mismatch with the Issues snapshot")
    return {
        "schemaVersion": 3,
        "purpose": "Small, generated 4LEAF conversation handoff; NOT a second ledger",
        "sourceOfTruth": "GitHub Issues [4LEAF][ID]",
        "statusSnapshot": str(OUTPUT),
        "legacyEvidence": "apps/4leaf/rog/docs/RESTORATION_LEDGER.json",
        "activeFocus": selected,
        "counts": status["counts"],
        "openTasks": [{
            "id": task["id"], "issue": task["issue"],
            "priority": task["priority"], "title": task["title"],
            "status": task["status"], "url": task["url"]
        } for task in current],
        "rules": [
            "Read only this handoff and the focused Issue at session start",
            "Do not load the 628KB legacy JSON, historical chat, or long CI logs",
            "A merged PR is not a newly completed restoration task",
            "Check main, real browsers, original evidence and public Pages before closure"
        ]
    }


def github_issues(repo, token):
    if not token:
        raise ValueError("GITHUB_TOKEN is required; refusing unauthenticated partial sync")
    url = "https://api.github.com/search/issues"
    collected = []
    page = 1
    while True:
        query = urllib.parse.urlencode({
            "q": f"repo:{repo} is:issue in:title 4LEAF",
            "per_page": 100,
            "page": page,
        })
        req = urllib.request.Request(url + "?" + query, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "4leaf-ledger-sync/1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
        if result.get("incomplete_results"):
            raise ValueError("GitHub search is incomplete; refusing partial sync")
        batch = result.get("items", [])
        collected.extend(batch)
        if len(batch) < 100:
            break
        if page >= 10:
            raise ValueError("GitHub search result cap reached")
        page += 1
    return collected


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY",
                                                      "koith/browser-app-lab"))
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--input-json", type=Path,
                   help="Offline fixture for tests; not used by production workflow")
    p.add_argument("--handoff-output", type=Path, default=HANDOFF)
    p.add_argument("--focus-input", type=Path, default=FOCUS)
    args = p.parse_args()
    items = (json.loads(args.input_json.read_text(encoding="utf-8"))
             if args.input_json else github_issues(args.repo, os.environ.get("GITHUB_TOKEN")))
    previous = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
    out = convert(items, previous)
    focus = json.loads(args.focus_input.read_text(encoding="utf-8"))
    handoff = json.dumps(make_handoff(out, focus), ensure_ascii=False, indent=2) + "\n"
    payload = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if previous is None or args.output.read_text(encoding="utf-8") != payload:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    args.handoff_output.parent.mkdir(parents=True, exist_ok=True)
    if not args.handoff_output.exists() or args.handoff_output.read_text(encoding="utf-8") != handoff:
        args.handoff_output.write_text(handoff, encoding="utf-8")
    print("4LEAF status: " + json.dumps(out["counts"], ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print("4LEAF sync failed: " + str(error), file=sys.stderr)
        sys.exit(1)
