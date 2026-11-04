"""No-charge event-driven progression checks. No network or account credentials."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "event_pipeline", Path(__file__).with_name("intersection_event_pipeline.py")
)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SHA = "e" * 40
REPO = "koith/browser-app-lab"
ISSUE = "\n".join(f"- [ ] **INT-{i:02d}** task" for i in range(1, 11))


def row(id_, *, status="completed", conclusion="success", sha=SHA):
    return {"id": id_, "status": status, "conclusion": conclusion,
            "head_sha": sha, "event": "workflow_dispatch"}


def trigger(name, *, conclusion="success", id_=123):
    return {"id": id_, "name": name, "conclusion": conclusion}


class EventDrivenTests(unittest.TestCase):
    def test_priority_does_not_change_without_checkbox(self):
        self.assertEqual(p.first_incomplete(ISSUE), ("INT-01", "OPEN"))
        self.assertEqual(p.first_incomplete(ISSUE.replace(
            "- [ ] **INT-01**", "- [x] **INT-01**"
        )), ("INT-02", "OPEN"))
        self.assertEqual(p.first_incomplete("")[-1], "MISSING_FROM_ISSUE")

    def test_trust_only_main_completed_repo_owned_runs(self):
        clean = {"workflow_run": {"id": 123, "name":
                 "INTERSECTION — Immediate Encrypted TeraBox Recovery",
                 "status": "completed", "head_branch": "main",
                 "event": "workflow_dispatch",
                 "head_repository": {"full_name": REPO}}}
        self.assertTrue(p.trustworthy_event("workflow_run", clean, REPO))
        self.assertFalse(p.trustworthy_event("workflow_run", {
            "workflow_run": {**clean["workflow_run"], "event": "pull_request"}
        }, REPO))
        self.assertFalse(p.trustworthy_event("workflow_run", {
            "workflow_run": {**clean["workflow_run"],
                             "head_repository": {"full_name": "attacker/fork"}}
        }, REPO))
        self.assertFalse(p.trustworthy_event("issues", {
            "action": "edited", "issue": {"number": 999}
        }, REPO))

    def test_replay_success_starts_repair_without_elapsed_timer(self):
        t = trigger("INTERSECTION — Immediate Encrypted TeraBox Recovery")
        decision = p.decide("INT-01", t, SHA, {p.REPAIR: []})
        self.assertEqual(decision["action"], "DISPATCH")
        self.assertEqual(decision["workflow"], p.REPAIR)
        self.assertNotIn("cooldown", str(decision).lower())

    def test_duplicate_or_failed_replay_never_causes_loop(self):
        t = trigger("INTERSECTION — Immediate Encrypted TeraBox Recovery")
        active = p.decide("INT-01", t, SHA, {
            p.REPAIR: [row(124, status="pending")]
        })
        self.assertEqual(active["action"], "NONE")
        self.assertEqual(active["reason"], "REPAIR_ALREADY_IN_PROGRESS")
        attempted = p.decide("INT-01", t, SHA, {
            p.REPAIR: [row(124, conclusion="failure")]
        })
        self.assertEqual(attempted["reason"], "REPAIR_ALREADY_ATTEMPTED_AFTER_REPLAY")
        failed = p.decide("INT-01", trigger(t["name"],
                          conclusion="failure"), SHA, {p.REPAIR: []})
        self.assertEqual(failed["action"], "NONE")
        self.assertEqual(failed["reason"], "RECOVERY_FAILED_REQUIRES_CODE_REPAIR")

    def test_code_pass_alone_never_completes_int01(self):
        d = p.decide("INT-01", trigger(
            "INTERSECTION — Verify and Rebuild Private TeraBox Archive"
        ), SHA, {})
        self.assertEqual(d["action"], "NONE")
        self.assertIn("UNVERIFIED", d["reason"])

    def test_next_task_runs_qa_only_if_no_same_commit_run(self):
        d = p.decide("INT-02", {}, SHA, {p.QA_FOR_TASK["INT-02"]: []})
        self.assertEqual(d["action"], "DISPATCH")
        self.assertEqual(d["workflow"], p.QA_FOR_TASK["INT-02"])
        known = {p.QA_FOR_TASK["INT-02"]: [row(44)]}
        d2 = p.decide("INT-02", {}, SHA, known)
        self.assertEqual(d2["action"], "NONE")
        failed = {p.QA_FOR_TASK["INT-02"]: [
            row(44, conclusion="failure")]}
        d3 = p.decide("INT-02", {}, SHA, failed)
        self.assertEqual(d3["reason"], "QA_FAILED_FIX_CODE_BEFORE_RERUN")
        # Changing source commit after repair allows a new QA without a timer.
        d4 = p.decide("INT-02", {}, "f" * 40, failed)
        self.assertEqual(d4["action"], "DISPATCH")

    def test_web_task_requires_qa_then_deployment_then_browser(self):
        qa = p.QA_FOR_TASK["INT-10"]
        env = {qa: [row(11)], p.PAGES: [], p.DEPLOYED_QA: []}
        wait = p.decide("INT-10", {}, SHA, env)
        self.assertEqual(wait["reason"], "WAIT_FOR_PAGES_DEPLOY_ON_SAME_COMMIT")
        env[p.PAGES] = [row(12)]
        step = p.decide("INT-10", {}, SHA, env)
        self.assertEqual(step["action"], "DISPATCH")
        self.assertEqual(step["workflow"], p.DEPLOYED_QA)
        env[p.DEPLOYED_QA] = [row(13)]
        final = p.decide("INT-10", {}, SHA, env)
        self.assertEqual(final["action"], "NONE")
        self.assertIn("FINAL_PRODUCT_GATE_PENDING", final["reason"])

    def test_disabled_old_timers_not_present_in_pipeline(self):
        source = Path(__file__).with_name("intersection_event_pipeline.py").read_text()
        self.assertNotIn("timedelta(", source)
        self.assertNotIn("sleep(", source)
        self.assertNotIn("COOLDOWN =", source)
        self.assertNotIn("schedule:", source)


if __name__ == "__main__":
    unittest.main()
