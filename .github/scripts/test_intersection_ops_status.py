"""Offline, credential-free acceptance checks of the operations status reporter."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "intersection_ops_status", Path(__file__).with_name("intersection_ops_status.py")
)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
REPO = "koith/browser-app-lab"


def run(rid, conclusion="failure", status="completed", event="schedule"):
    return {"id": rid, "status": status, "conclusion": conclusion, "event": event}


class StatusBoardTests(unittest.TestCase):
    def test_only_whitelisted_aggregate_fields_render(self):
        logs = (
            '2026-11-04Z DEMAND_CAPTURE_AGGREGATE_ONLY '
            '{"fetched":42,"saved_verified":3,"storage_failures":21,'
            '"encrypted_only_originals":21,"operational_status":"DEGRADED_STORAGE",'
            '"text":"private source never published",'
            '"user_id":"untrusted user"}'
        )
        metrics = ops.sanitized_metrics(logs, "DEMAND_CAPTURE_AGGREGATE_ONLY")
        self.assertEqual(metrics["storage_failures"], 21)
        self.assertEqual(metrics["saved_verified"], 3)
        self.assertNotIn("text", metrics)
        self.assertNotIn("user_id", metrics)
        self.assertIsNone(ops.sanitized_metrics(
            "raw private content with no aggregate marker",
            "DEMAND_CAPTURE_AGGREGATE_ONLY"
        ))

    def test_suspicious_negative_string_and_large_counts_refused(self):
        text = ('DEMAND_CAPTURE_AGGREGATE_ONLY '
                '{"fetched":-4,"storage_failures":"0",'
                '"saved_verified":1000000001,"encrypted_only_originals":true}')
        self.assertEqual(
            ops.sanitized_metrics(text, "DEMAND_CAPTURE_AGGREGATE_ONLY"), {}
        )

    def test_failed_latest_capture_is_not_hidden_by_older_pass(self):
        groups = {
            ops.CAPTURE: [run(9), run(8, "success"), run(7, "success")],
            ops.REPLAY: [run(10, status="pending", conclusion=None)],
            ops.REPAIR: [],
        }
        summary = {
            9: {"fetched": 42, "saved_verified": 3,
                "storage_failures": 21, "encrypted_only_originals": 21},
            8: {"fetched": 2, "saved_verified": 2,
                "storage_failures": 0, "encrypted_only_originals": 0},
            7: {"fetched": 4, "saved_verified": 4,
                "storage_failures": 0, "encrypted_only_originals": 0},
        }
        body = ("- [ ] **INT-01 테라박스 저장 장애**\n"
                "- [x] **INT-02 예약 확인**\n")
        result = ops.render(REPO, groups, summary, body, datetime(
            2026, 11, 4, tzinfo=timezone.utc
        ))
        self.assertIn("P0 / INT-01: FAILED", result)
        self.assertIn("1/2건 완료 표시", result)
        self.assertIn("21", result)
        self.assertIn("PENDING", result)
        self.assertIn("과거 미복구 0건", result)
        self.assertIn(ops.MARKER, result)
        self.assertNotIn("private source", result)

    def test_three_clean_captures_never_claims_total_backlog_restoration(self):
        captures = [run(i, "success") for i in (7, 6, 5)]
        summary = {i: {"storage_failures": 0, "encrypted_only_originals": 0}
                   for i in (7, 6, 5)}
        result = ops.render(
            REPO, {ops.CAPTURE: captures, ops.REPLAY: [], ops.REPAIR: []},
            summary, "", datetime(2026, 11, 4, tzinfo=timezone.utc),
        )
        self.assertIn("UNVERIFIED", result)
        self.assertNotIn("P0 / INT-01: VERIFIED", result)

    def test_missing_logs_are_unknown_not_zero(self):
        result = ops.render(
            REPO,
            {ops.CAPTURE: [run(4, "success")], ops.REPLAY: [], ops.REPAIR: []},
            {}, "", datetime(2026, 11, 4, tzinfo=timezone.utc)
        )
        self.assertIn("미검증", result)
        self.assertNotIn("P0 / INT-01: VERIFIED", result)

    def test_non_user_input_workflow_urls_are_canonical(self):
        self.assertEqual(
            ops.run_url(run(42), REPO),
            "https://github.com/koith/browser-app-lab/actions/runs/42"
        )
        self.assertEqual(ops.safe_run_status(run(4, "failure")), "FAILURE")


if __name__ == "__main__":
    unittest.main()
