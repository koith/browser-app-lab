"""Offline regression checks for the 4LEAF Issue ledger sync."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "sync_restoration_issues", HERE / "sync_restoration_issues.py"
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def issue(number, name, state="open", body="**우선순위:** P0"):
    return {
        "number": number,
        "title": "[4LEAF][" + name + "] sample",
        "state": state,
        "body": body,
        "html_url": "https://github.com/koith/browser-app-lab/issues/" + str(number),
    }


class LedgerSyncTest(unittest.TestCase):
    def test_active_vs_legacy_complete(self):
        current = issue(1, "M01", "open")
        old_done = issue(2, "M02", "closed", "- 기존 상태: done")
        result = sync.convert([current, old_done])
        self.assertEqual(result["counts"]["done"], 1)
        self.assertEqual(result["counts"]["remaining"], 1)
        self.assertEqual(result["counts"]["total"], 2)

    def test_todo_import(self):
        item = issue(3, "M03", "open", "**원장 상태:** todo")
        self.assertEqual(sync.convert([item])["tasks"][0]["status"], "todo")

    def test_unverified_closed_is_not_done(self):
        item = issue(4, "M04", "closed")
        row = sync.convert([item])["tasks"][0]
        self.assertEqual(row["status"], "review_required")
        self.assertEqual(sync.convert([item])["counts"]["done"], 0)

    def test_closed_with_acceptance_marker_and_link(self):
        item = issue(4, "M04", "closed",
                     "<!-- 4LEAF-ACCEPTED-WITH-EVIDENCE --> "
                     "https://github.com/koith/browser-app-lab/pull/100")
        self.assertEqual(sync.convert([item])["tasks"][0]["status"], "done")

    def test_duplicate_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            sync.convert([issue(5, "M01"), issue(6, "M01")])

    def test_missing_prior_work_fails_closed(self):
        previous = {"tasks": [{"id": "M01"}, {"id": "M02"}]}
        with self.assertRaisesRegex(ValueError, "disappeared"):
            sync.convert([issue(7, "M01")], previous)

    def test_irrelevant_issue_and_pr_are_skipped(self):
        ordinary = issue(8, "M01")
        ordinary["title"] = "[OTHER][M01] non-4leaf"
        pr = issue(9, "M02")
        pr["pull_request"] = {}
        result = sync.convert([ordinary, pr, issue(10, "M03")])
        self.assertEqual(result["counts"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
