#!/usr/bin/env python3
"""Bounded, read-only audit of ALL gallery GitHub Actions workflow triggers.

This inventories workflows, not images. A passing audit does not prove any
new photo was downloaded, saved or made visible in the published gallery.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
PREFIXES = ("gallery-", "mimmi-", "yui-")
EVENTS = ("push", "pull_request", "workflow_dispatch", "workflow_run", "schedule", "workflow_call")
STATIC = "Deploy static content to Pages"
NATIVE = "pages build and deployment"
# These three historic subscriptions are an intentional two-publisher fallback.
# Do not remove either hook without a proven equivalent post-deployment trigger.
KNOWN_DUAL_HOOKS = {
    "gallery-deployed-pages-photo-qa.yml",
    "gallery-g05-new-sns-live.yml",
    "gallery-new20-cross-existing-visual-audit.yml",
}


def trigger_block(content: str) -> str:
    match = re.search(r"(?ms)^on:[^\n]*\n(.*?)(?=^[a-zA-Z][\w-]*:|\Z)", content)
    if not match:
        raise ValueError("Missing block-style on: declaration")
    return match.group(1)


def audit_text(content: str) -> dict:
    section = trigger_block(content)
    events = [name for name in EVENTS if re.search(r"(?m)^  " + re.escape(name) + r":", section)]
    if not events:
        raise ValueError("No recognized workflow triggers")
    crons = re.findall(r"(?m)^\s+- cron:\s*['\"]?([^'\"]+)", section)
    return {
        "events": events,
        "static_and_native": "workflow_run" in events and STATIC in section and NATIVE in section,
        "static_deploy_hook": "workflow_run" in events and STATIC in section,
        "native_deploy_hook": "workflow_run" in events and NATIVE in section,
        "crons": crons,
        "high_frequency_schedule": any(
            len(part.split(",")) >= 6 for cron in crons for part in cron.split()[:1]
        ),
    }


def audit_all() -> dict:
    paths = sorted(p for p in WORKFLOWS.glob("*.yml") if p.name.startswith(PREFIXES))
    paths.extend(p for p in WORKFLOWS.glob("*.yaml") if p.name.startswith(PREFIXES))
    result = {"total": len(paths), "events": {}, "manual_only": 0,
              "scheduled": [], "dual_deploy_hooks": [], "static_only_deploy_hooks": [],
              "high_frequency_schedule": [], "invalid": []}
    for path in sorted(paths):
        try:
            info = audit_text(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            result["invalid"].append({"name": path.name, "error": str(error)})
            continue
        for event in info["events"]:
            result["events"][event] = result["events"].get(event, 0) + 1
        if info["events"] == ["workflow_dispatch"]:
            result["manual_only"] += 1
        if info["crons"]:
            result["scheduled"].append({"name": path.name, "cron": info["crons"]})
        if info["static_and_native"]:
            result["dual_deploy_hooks"].append(path.name)
        if info["static_deploy_hook"] and not info["native_deploy_hook"]:
            result["static_only_deploy_hooks"].append(path.name)
        if info["high_frequency_schedule"]:
            result["high_frequency_schedule"].append(path.name)
    return result


def self_test() -> None:
    a = audit_text("name: test\non:\n  workflow_dispatch:\n  workflow_run:\n"
                   "    workflows: ['Deploy static content to Pages', 'pages build and deployment']\n"
                   "    types: [completed]\npermissions:\n  contents: read\n")
    assert a["static_and_native"] and len(a["events"]) == 2, a
    b = audit_text("on:\n  schedule:\n    - cron: '7,17,27,37,47,57 * * * *'\njobs:\n  x:\n")
    assert b["high_frequency_schedule"] and not b["static_and_native"], b
    c = audit_text("on:\n  pull_request:\n    paths:\n      - 'apps/yui-gallery/**'\n"
                   "  workflow_dispatch:\npermissions:\n  contents: read\n")
    assert c["events"] == ["pull_request", "workflow_dispatch"], c
    print("GALLERY_WORKFLOW_AUDIT_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    result = audit_all()
    print("GALLERY_WORKFLOW_AUDIT " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("### Gallery workflows: bounded full inventory\n")
            out.write(f"- Inventory: {result['total']} (gallery-/mimmi-/yui-)\n")
            out.write(f"- Events: {result['events']}\n")
            out.write(f"- Manual-only: {result['manual_only']}\n")
            out.write(f"- Scheduled: {len(result['scheduled'])}\n")
            out.write(f"- Dual publisher fallbacks (not proven duplicate executions): {result['dual_deploy_hooks']}\n")
            out.write(f"- Legacy static-only post-deploy hooks (review separately): {result['static_only_deploy_hooks']}\n")
            out.write(f"- High-frequency scheduled workflows: {result['high_frequency_schedule']}\n")
            out.write("- Actual newly saved original photos: NOT_MEASURED_BY_THIS_AUDIT\n")
    if args.strict:
        errors = []
        if result["total"] < 140:
            errors.append("Unexpected large gallery workflow inventory loss")
        if result["invalid"]:
            errors.append(f"Unreadable workflow trigger definitions: {result['invalid']}")
        new_hooks = set(result["dual_deploy_hooks"]) - KNOWN_DUAL_HOOKS
        if new_hooks:
            errors.append(f"New dual publisher hooks require evidence-based review: {sorted(new_hooks)}")
        if len(result["scheduled"]) > 4:
            errors.append("New recurring scheduled workflow needs explicit budget review")
        if errors:
            raise SystemExit("GALLERY_WORKFLOW_BUDGET_FAIL: " + "; ".join(errors))
        print("GALLERY_WORKFLOW_BUDGET_PASS")


if __name__ == "__main__":
    main()
