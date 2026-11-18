"""Deterministic no-network tests for bounded INTERSECTION resume summaries."""
import unittest

from intersection_compact_handoff import summarize

BODY = "\n".join(
    f"- [{'x' if i==10 else ' '}] **INT-{i:02}** 작업 {i}: "
    "비밀처럼 보이는 긴 설명이나 URL은 이어받기에 복사하지 않는다"
    for i in range(1, 11)
)


class HandoffTests(unittest.TestCase):
    def test_bound_and_next_priority(self):
        report = summarize(BODY, "abcdef123456789")
        self.assertIn("완료 **1** / 미완료 **9**", report)
        self.assertIn("INT-01", report)
        self.assertNotIn("비밀처럼", report)
        self.assertLessEqual(len(report), 1100)
        self.assertIn("abcdef123456", report)

    def test_no_unverified_completion_inference(self):
        report = summarize(BODY.replace("- [ ] **INT-01**",
                                        "- [x] **INT-01**"))
        self.assertIn("완료 **2** / 미완료 **8**", report)
        self.assertIn("INT-02", report)
        self.assertIn("실사용·원본 SHA·배포 검증은 별도로 필요", report)

    def test_reject_missing_duplicate_and_out_of_bounds(self):
        with self.assertRaises(ValueError):
            summarize(BODY.split("\n", 1)[1])
        with self.assertRaises(ValueError):
            summarize(BODY.replace("INT-10", "INT-09"))
        with self.assertRaises(ValueError):
            summarize(BODY.replace("INT-10", "INT-99"))

    def test_ignore_historical_checkboxes_and_sanitize_markdown(self):
        report = summarize(BODY + "\n- [x] **INT-01** extra historical record")
        with self.assertRaises(ValueError):
            summarize(BODY + "\n- [x] **INT-01** extra historical record")
        self.assertLessEqual(len(report), 1100)


if __name__ == "__main__":
    unittest.main()
