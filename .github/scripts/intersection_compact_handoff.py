"""Bounded, evidence-honest resume summary for INTERSECTION Actions.

Derives status solely from the current #607 issue body, never from historic
comments or logs; does not store a second mutable backlog.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ISSUE_URL = "https://github.com/koith/browser-app-lab/issues/607"
TASK = re.compile(r"^- \[([ xX])\] \*\*(INT-(\d{2}))\*\*\s+([^\n]*)$", re.M)
MAX_SUMMARY = 1100


def summarize(body: str, sha: str = "") -> str:
    rows = []
    for match in TASK.finditer(body):
        checked, code, number, title = match.groups()
        if not 1 <= int(number) <= 10:
            continue
        # Never include raw long issue details, secrets, URLs or old logs.
        title = re.split(r"[:：—–]", title, maxsplit=1)[0]
        title = re.sub(r"[^가-힣a-zA-Z0-9_·/()\s-]", "", title)
        rows.append((code, checked.lower() == "x", " ".join(title.split())[:64]))
    if len(rows) != 10 or len({item[0] for item in rows}) != 10:
        raise ValueError("expected exactly ten unique current INT-01..10 checklist rows")
    rows.sort(key=lambda item: int(item[0][-2:]))
    if [x[0] for x in rows] != [f"INT-{x:02d}" for x in range(1, 11)]:
        raise ValueError("incomplete canonical INT-01..10")
    done = sum(1 for _, ok, _ in rows if ok)
    priority = next(((code, title) for code, ok, title in rows
                     if not ok and int(code[-2:]) <= 4), None)
    if priority is None:
        priority = next(((code, title) for code, ok, title in rows
                         if not ok), None)
    commit = re.sub(r"[^a-f0-9]", "", sha.lower())[:12] or "확인 불가"
    lines = [
        "### 교집합 짧은 이어받기 (자동 산출)",
        f"- 정본: [개발원장 #607]({ISSUE_URL})",
        f"- 현재 체크박스: 완료 **{done}** / 미완료 **{10-done}** (총 10)",
        "- 우선 확인: " + (f"{priority[0]} — {priority[1]}" if priority else "핵심 체크박스 전부 완료"),
        f"- 검토 대상 커밋: `{commit}`",
        "- 판정: 체크 상태만 확인. 실사용·원본 SHA·배포 검증은 별도로 필요",
        "- 다음 실행: 해당 ID의 관련 코드·최신 실패 단계만 선택적으로 읽고 수정→테스트→배포 검증",
        "- 읽지 말 것: 이전 대화 전문, 과거 댓글 71개, 역사 원장, 전체 CI 로그",
    ]
    result = "\n".join(lines) + "\n"
    if len(result) > MAX_SUMMARY:
        raise ValueError("handoff exceeded output budget")
    return result


def main() -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    try:
        proc = subprocess.run(
            ["gh", "api", "/repos/koith/browser-app-lab/issues/607"],
            capture_output=True, text=True, check=True, timeout=20)
        if len(proc.stdout) > 150_000:
            raise ValueError("issue payload exceeded safe limit")
        body = json.loads(proc.stdout).get("body")
        if not isinstance(body, str):
            raise ValueError("missing current issue body")
        report = summarize(body, os.getenv("GITHUB_SHA", ""))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        report = (
            "### 교집합 짧은 이어받기 — UNVERIFIED\n"
            f"- 정본: [개발원장 #607]({ISSUE_URL})\n"
            "- 현재 본문을 읽지 못했으므로 완료 수와 다음 작업을 추정하지 않습니다.\n"
        )
    with Path(summary_path).open("a", encoding="utf-8") as out:
        out.write("\n" + report)
    print("INTERSECTION_COMPACT_HANDOFF",
          "VERIFIED" if "UNVERIFIED" not in report else "UNVERIFIED",
          "chars", len(report), flush=True)


if __name__ == "__main__":
    main()
