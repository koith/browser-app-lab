"""Offline acceptance gates for the safe controller."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "controller", Path(__file__).with_name("intersection_autonomous_controller.py")
)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
NOW = datetime(2026, 11, 4, 2, tzinfo=timezone.utc)
BODY = "\n".join(
    f"- [ ] **INT-{n:02d}** work item" for n in range(1, 11)
)


def run(rid, status="completed", conclusion="failure", hours=1):
    return {"id": rid, "status": status, "conclusion": conclusion,
            "created_at": (NOW - timedelta(hours=hours)).isoformat()}


class ControllerTests(unittest.TestCase):
    def test_first_incomplete_is_not_historical_subtask(self):
        self.assertEqual(c.first_incomplete(BODY), ("INT-01", "OPEN"))
        updated = BODY.replace("**INT-01**", "**INT-01**", 1).replace(
            "- [ ] **INT-01**", "- [x] **INT-01**", 1
        )
        self.assertEqual(c.first_incomplete(updated), ("INT-02", "OPEN"))

    def test_no_duplicate_recovery_even_if_old_and_pending(self):
        state = c.decide(BODY, [run(12)], [
            run(10, status="pending", hours=20)
        ], NOW)
        self.assertEqual(state["action"], "NONE")
        self.assertEqual(state["reason"], "RECOVERY_ALREADY_QUEUED_OR_RUNNING")

    def test_dispatch_only_after_six_hours_with_failed_capture(self):
        result = c.decide(BODY, [run(12)], [run(10, hours=7)], NOW)
        self.assertEqual(result["action"], "DISPATCH_RECOVERY")
        self.assertEqual(result["source_run_id"], 12)

    def test_recent_replay_and_successful_capture_do_not_dispatch(self):
        self.assertEqual(
            c.decide(BODY, [run(12)], [run(10, hours=2)], NOW)["reason"],
            "RECOVERY_COOLDOWN"
        )
        self.assertEqual(
            c.decide(BODY, [run(12, conclusion="success")],
                     [run(10, hours=7)], NOW)["action"],
            "NONE"
        )

    def test_never_progress_without_checked_int01(self):
        updated = BODY.replace("- [ ] **INT-01**", "- [x] **INT-01**")
        state = c.decide(updated, [run(12)], [run(10, hours=7)], NOW)
        self.assertEqual(state["task"], "INT-02")
        self.assertEqual(state["action"], "NONE")

    def test_after_verified_issue_gate_only_allowlisted_qa_can_start(self):
        updated = BODY.replace("- [ ] **INT-01**", "- [x] **INT-01**")
        result = c.decide(updated, [run(12)], [run(10, hours=7)],
                          NOW, qa_runs=[run(4, hours=30)])
        self.assertEqual(result["task"], "INT-02")
        self.assertEqual(result["action"], "DISPATCH_QA")
        self.assertEqual(result["workflow"], "demand-public-sources-probe.yml")
        self.assertNotIn("INT-01", result["workflow"])

    def test_next_task_qa_is_rate_limited_and_never_auto_checked(self):
        updated = BODY.replace("- [ ] **INT-01**", "- [x] **INT-01**")
        pending = c.decide(updated, [run(12)], [],
                           NOW, qa_runs=[run(4, "pending", hours=40)])
        self.assertEqual(pending["action"], "NONE")
        self.assertEqual(pending["reason"], "QA_ALREADY_QUEUED_OR_RUNNING")
        cooldown = c.decide(updated, [run(12)], [],
                            NOW, qa_runs=[run(4, hours=2)])
        self.assertEqual(cooldown["reason"], "QA_COOLDOWN")

    def test_missing_task_and_missing_evidence_fail_closed(self):
        self.assertEqual(c.first_incomplete("")[1], "MISSING_FROM_ISSUE")
        self.assertEqual(c.decide(BODY, [], [], NOW)["action"], "NONE")
        self.assertEqual(
            c.decide(BODY, [run(12, hours=9)], [], NOW)["action"], "NONE"
        )

    def test_all_checked_is_not_automatically_verified(self):
        all_done = "\n".join(f"- [x] **INT-{n:02d}** task"
                             for n in range(1, 13))
        state = c.decide(all_done, [run(12)], [], NOW)
        self.assertEqual(state["action"], "NONE")
        self.assertEqual(state["task_state"], "ALL_CHECKED_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
