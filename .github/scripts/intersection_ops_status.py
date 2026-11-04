"""Single-comment, evidence-only INTERSECTION status board.

The bot runs inside GitHub Actions, never creates ChatGPT conversations, never
downloads private original artifacts and never publishes source posts, accounts,
remote paths or raw backend errors. It reports only whitelisted aggregate data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ISSUE_NUMBER = 607
MARKER = "<!-- intersection-evidence-status-v1 -->"
PREFIX = "https://api.github.com"
CAPTURE = "demand-fast-capture.yml"
REPLAY = "demand-replay-encrypted.yml"
REPAIR = "demand-repair-archive.yml"
CONTROLLER = "intersection-autonomous-controller.yml"
METRICS = {
    "DEMAND_CAPTURE_AGGREGATE_ONLY": (
        "fetched", "saved_verified", "storage_failures",
        "encrypted_only_originals", "duplicates", "operational_status",
    ),
    "INTERSECTION_ENCRYPTED_RECOVERY_SUMMARY": (
        "artifacts", "post_and_media_verified", "first_observation_verified",
        "buffer_failures", "deferred_buffers", "deferred_artifacts",
        "batch_sha_verified",
    ),
    "INTERSECTION_EVENT_PIPELINE": ("task", "action", "reason"),
}
# Only fixed known internal stage codes may appear in public issue comments.
ALLOWED_STAGE_REASONS = frozenset(["INT01_OPERATIONAL_PROOF_PENDING","RECOVERY_FAILED_REQUIRES_CODE_REPAIR", "SYNTHETIC_DIAGNOSTIC_ALREADY_RUNNING", "DIAGNOSTIC_ALREADY_TRIED_ON_SAME_CODE", "RECOVERY_FAILED_TRY_SAFE_CLOUD_DIAGNOSTIC", "SYNTHETIC_DIAGNOSTIC_FAILED_WAIT_CODE_FIX", "RECOVERY_ALREADY_QUEUED_OR_RUNNING", "RECOVERY_ALREADY_ATTEMPTED_AFTER_DIAGNOSTIC", "DIAGNOSTIC_PASS_REPLAY_ENCRYPTED_ORIGINALS","REPAIR_ALREADY_IN_PROGRESS","REPAIR_ALREADY_ATTEMPTED_AFTER_REPLAY","RECOVERY_COMPLETE_START_REMOTE_RECONCILIATION","REBUILD_PASS_FULL_HISTORICAL_GATE_STILL_UNVERIFIED","REBUILD_FAILED_REQUIRES_CODE_REPAIR","CAPTURE_COMPLETED_NATIVE_REPLAY_HANDLES_FAILED_RUNS","NO_TRUSTED_TASK_QA_IMPLEMENTED","TASK_QA_IN_PROGRESS","VERIFIED_PREDECESSOR_START_TASK_QA","QA_FAILED_FIX_CODE_BEFORE_RERUN","TASK_QA_NOT_YET_VERIFIED","TASK_QA_PASS_PRODUCT_ACCEPTANCE_STILL_REQUIRED","WAIT_FOR_PAGES_DEPLOY_ON_SAME_COMMIT","DEPLOYED_BROWSER_QA_PASS_FINAL_PRODUCT_GATE_PENDING","DEPLOYED_BROWSER_QA_IN_PROGRESS","PAGES_PASS_START_DEPLOYED_BROWSER_QA","DEPLOYED_QA_PASS_FINAL_PRODUCT_GATE_PENDING","DEPLOYED_QA_FAILED_REQUIRES_CODE_FIX","ISSUE_TASK_CHECKBOX_MISSING_FAIL_CLOSED","UNTRUSTED_OR_UNRELATED_EVENT","NO_OPEN_TASK_VERIFIED"])
ALLOWED_STAGE_ACTIONS = frozenset(("NONE", "STAGE_DISPATCHED"))
VALID_STATUS = {"success", "failure", "cancelled", "timed_out", "skipped", "neutral"}


def sanitized_metrics(text, marker):
    """Extract counters only; never expose untrusted raw log text."""
    allow = METRICS[marker]
    found = None
    for line in text.splitlines():
        needle = marker + " "
        if needle not in line:
            continue
        try:
            payload = json.loads(line.split(needle, 1)[1].strip())
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        result = {}
        for name in allow:
            value = payload.get(name)
            if isinstance(value, bool):
                continue
            if isinstance(value, int) and 0 <= value <= 1_000_000_000:
                result[name] = value
            if name == "operational_status" and value in (
                "VERIFIED_POSTS", "JOURNAL_ONLY", "DEGRADED_STORAGE",
                "DEGRADED_INDEX", "DEGRADED_MEDIA",
            ):
                result[name] = value
            if marker == "INTERSECTION_EVENT_PIPELINE" and isinstance(value, str):
                if name == "task" and re.fullmatch(r"INT-(?:0[1-9]|1[0-2])", value):
                    result[name] = value
                elif name == "action" and value in ALLOWED_STAGE_ACTIONS:
                    result[name] = value
                elif name == "reason" and value in ALLOWED_STAGE_REASONS:
                    result[name] = value
        found = result
    return found


def safe_run_status(run):
    """Actions conclusion is not a proof that any originals were saved."""
    if not isinstance(run, dict):
        return "UNVERIFIED"
    status = run.get("status")
    conclusion = run.get("conclusion")
    if status != "completed":
        return str(status).upper() if status in (
            "queued", "pending", "in_progress", "waiting", "requested"
        ) else "UNVERIFIED"
    return str(conclusion).upper() if conclusion in VALID_STATUS else "UNVERIFIED"


def run_url(run, repo):
    number = run.get("id")
    return (f"https://github.com/{repo}/actions/runs/{number}"
            if isinstance(number, int) and number > 0 else "")


def render(repo, run_groups, summaries, issue_body, now):
    """Render one durable status comment without claiming unproven completion."""
    latest_capture = next(iter(run_groups.get(CAPTURE, [])), None)
    capture_rows = run_groups.get(CAPTURE, [])[:3]
    recovery_rows = run_groups.get(REPLAY, [])[:3]
    repair_rows = run_groups.get(REPAIR, [])[:2]
    controller_rows = run_groups.get(CONTROLLER, [])[:1]
    controller_metrics = (
        summaries.get(controller_rows[0]["id"], {}) if controller_rows else {}
    )
    controller_task = controller_metrics.get("task", "미검증")
    controller_reason = controller_metrics.get("reason", "UNVERIFIED")
    statuses = []
    for row in capture_rows:
        data = summaries.get(row["id"])
        statuses.append(
            row.get("status") == "completed"
            and row.get("conclusion") == "success"
            and data is not None and data.get("storage_failures") == 0
            and data.get("encrypted_only_originals") == 0
        )
    streak = len(statuses) == 3 and all(statuses)
    recent_errors = any(
        row.get("status") == "completed" and row.get("conclusion") != "success"
        for row in capture_rows
    )
    if recent_errors:
        core = "FAILED — 최근 실제 수집 실패가 확인됨"
    elif streak:
        core = "UNVERIFIED — 최근 3회 수집은 정상이나 전체 복구·무결성 미검증"
    else:
        core = "UNVERIFIED — 연속 정상 수집 및 기존 원본 전수 검증 미충족"
    titles = re.findall(
        r"(?m)^- \[([ x])\] \*\*(INT-[0-9]{2})(?:\s+|[^*])*\*\*",
        issue_body,
    )
    checked = {key for state, key in titles if state == "x"}
    tracked = {key for _, key in titles}
    extra = "INT-11, INT-12는 상세 OPERATIONS_BACKLOG.md에서 별도 관리. "
    lines = [
        MARKER,
        "## 교집합 자동 운영 진행판",
        f"마지막 점검: {now.strftime('%Y-%m-%d %H:%M UTC')} · GitHub Actions 자체 실행 · ChatGPT 새 대화 생성 없음",
        "",
        f"**P0 / INT-01: {core}**",
        f"**메인 이슈 체크:** {len(checked)}/{len(tracked) or '미확인'}건 완료 표시 · "
        "체크박스는 실제 복구 검증 없이는 자동 변경하지 않음",
        "",
        "### 최근 실제 수집 (최대 3회)",
        "| 실행 | 상태 | 발견 | 테라박스 검증 | 저장 실패 | 암호화 임시 보관 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for run in capture_rows:
        metrics = summaries.get(run["id"]) or {}
        ref = run_url(run, repo)
        link = f"[#{run['id']}]({ref})" if ref else "미확인"
        def metric(key):
            value = metrics.get(key)
            return str(value) if isinstance(value, int) else "미검증"
        lines.append(
            f"| {link} | {safe_run_status(run)} | {metric('fetched')} | "
            f"{metric('saved_verified')} | {metric('storage_failures')} | "
            f"{metric('encrypted_only_originals')} |"
        )
    if not capture_rows:
        lines.append("| 기록 없음 | UNVERIFIED | — | — | — | — |")
    lines.extend([
        "",
        "### 암호화 원본 복구 (최근 3회)",
        "| 실행 | 상태 | 글+미디어 검증 | 복구 실패 | 이월 버퍼 | 미처리 아티팩트 |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for run in recovery_rows:
        metrics = summaries.get(run["id"]) or {}
        link = f"[#{run['id']}]({run_url(run, repo)})"
        def metric(key):
            value = metrics.get(key)
            return str(value) if isinstance(value, int) else "미검증"
        lines.append(
            f"| {link} | {safe_run_status(run)} | {metric('post_and_media_verified')} | "
            f"{metric('buffer_failures')} | {metric('deferred_buffers')} | "
            f"{metric('deferred_artifacts')} |"
        )
    if not recovery_rows:
        lines.append("| 기록 없음 | UNVERIFIED | — | — | — | — |")
    lines.extend([
        "",
        "### 자율 복구·작업 선택 컨트롤러",
        " · ".join(
            f"[#{row['id']}]({run_url(row, repo)}) {safe_run_status(row)}"
            for row in controller_rows
        ) or "확인된 실행 없음",
        f"선택 일감: **{controller_task}** · 처리 단계: **{controller_reason}**",
        "이는 이벤트 기반 진행 상태입니다. 컨트롤러 실행 성공은 저장 장애 해결을 뜻하지 않음.",
        "",
        "### 유지보수 대기열",
        " · ".join(
            f"[#{row['id']}]({run_url(row, repo)}) {safe_run_status(row)}"
            for row in repair_rows
        ) or "확인된 실행 없음",
        "",
        "**다음 우선 작업:** " + (
            "INT-01 최근 저장 실패 원인과 암호화 보관본 복구를 먼저 해결"
            if recent_errors else
            "INT-01 미복구 암호화 원본 SHA256 전수 검증, 이후 INT-02 실제 수집 주기 확인"
        ),
        "",
        "완료 판정 조건: 원문과 정확한 원본 미디어의 테라박스 재읽기 SHA256, "
        "과거 미복구 0건, 다회차 저장 실패 0, 인덱스/실파일 일치. "
        "API 실행 성공이나 임시 암호화 보관만으로 완료 판정하지 않음.",
        "",
        extra + "비공개 원문·계정·자격증명·실파일명은 이 보고에 기록하지 않음.",
    ])
    return "\n".join(lines) + "\n"


class GitHub:
    def __init__(self, repo, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("invalid repository identifier")
        if not token:
            raise ValueError("GitHub Actions token unavailable")
        self.repo = repo
        self.token = token

    def request(self, path, *, method="GET", data=None, max_bytes=5_000_000):
        if not path.startswith("/"):
            raise ValueError("unsafe API path")
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = Request(
            PREFIX + path, data=body, method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "INTERSECTION-evidence-only-operations",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        with urlopen(req, timeout=25) as response:
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise ValueError("GitHub response exceeds private safety bound")
            return json.loads(payload) if payload else {}

    def workflow_runs(self, filename, limit=5):
        path = (
            f"/repos/{self.repo}/actions/workflows/{quote(filename, safe='')}"
            f"/runs?branch=main&per_page={limit}"
        )
        runs = self.request(path).get("workflow_runs", [])
        if not isinstance(runs, list):
            return []
        return [row for row in runs if isinstance(row, dict)
                and row.get("event") != "pull_request"][:limit]

    def metrics_for_run(self, run, marker, job_name):
        """Read only aggregated counters, or return unknown (never zero)."""
        try:
            jobs = self.request(
                f"/repos/{self.repo}/actions/runs/{run['id']}/jobs?per_page=30"
            ).get("jobs", [])
            selected = next(
                (job for job in jobs if job.get("name") == job_name), None
            )
            if not selected or selected.get("status") != "completed":
                return None
            job_id = selected.get("id")
            run_id = run.get("id")
            if (not isinstance(job_id, int) or job_id < 1
                    or not isinstance(run_id, int) or run_id < 1):
                return None
        except (HTTPError, URLError, OSError, ValueError, KeyError, StopIteration):
            return None

        # The REST job-log download may return a temporary redirected
        # artifact, which is sometimes unavailable to the Python URL client
        # despite the Actions run being readable. Use the locally available
        # authenticated GitHub CLI as an independent route in that case.
        try:
            req = Request(
                PREFIX + f"/repos/{self.repo}/actions/jobs/{job_id}/logs",
                headers={"Authorization": "Bearer " + self.token,
                         "Accept": "application/vnd.github+json"},
            )
            with urlopen(req, timeout=22) as response:
                payload = response.read(8_000_001)
            if len(payload) <= 8_000_000:
                metrics = sanitized_metrics(
                    payload.decode("utf-8", errors="replace"), marker
                )
                if metrics:
                    return metrics
        except (HTTPError, URLError, OSError, ValueError):
            pass

        try:
            # Fixed executable/arguments, validated numeric IDs, and
            # capture_output=True: raw logs, account names and credentials
            # never enter the public workflow log or GitHub issue comment.
            result = subprocess.run(
                ["gh", "run", "view", str(run_id),
                 "--job", str(job_id), "--log", "--repo", self.repo],
                capture_output=True, timeout=28, check=False,
            )
            if result.returncode == 0 and len(result.stdout) <= 8_000_000:
                metrics = sanitized_metrics(
                    result.stdout.decode("utf-8", errors="replace"), marker
                )
                if metrics:
                    return metrics
        except (OSError, subprocess.TimeoutExpired):
            pass
        # An absent summary, expired log or permission denial remains
        # UNVERIFIED; it must never turn into a false zero failure.
        return None

    def upsert_comment(self, body):
        existing = None
        for page in range(1, 5):
            comments = self.request(
                f"/repos/{self.repo}/issues/{ISSUE_NUMBER}/comments"
                f"?per_page=100&page={page}"
            )
            if not isinstance(comments, list):
                break
            for item in comments:
                author = item.get("user") or {}
                login = author.get("login", "")
                if (MARKER in item.get("body", "")
                        and (author.get("type") == "Bot"
                             or login == "github-actions[bot]")):
                    existing = item
                    break
            if existing or len(comments) < 100:
                break
        if existing:
            if existing.get("body") == body:
                return "unchanged"
            self.request(
                f"/repos/{self.repo}/issues/comments/{existing['id']}",
                method="PATCH", data={"body": body}
            )
            return "updated"
        self.request(
            f"/repos/{self.repo}/issues/{ISSUE_NUMBER}/comments",
            method="POST", data={"body": body}
        )
        return "created"


def main():
    gh = GitHub(
        os.getenv("GITHUB_REPOSITORY", ""),
        os.getenv("GH_TOKEN", ""),
    )
    issue = gh.request(f"/repos/{gh.repo}/issues/{ISSUE_NUMBER}")
    groups = {}
    summaries = {}
    for filename, marker, job in (
        (CAPTURE, "DEMAND_CAPTURE_AGGREGATE_ONLY", "capture"),
        (REPLAY, "INTERSECTION_ENCRYPTED_RECOVERY_SUMMARY", "replay"),
        (REPAIR, None, None),
        (CONTROLLER, "INTERSECTION_EVENT_PIPELINE", "safe-controller"),
    ):
        runs = gh.workflow_runs(filename, limit=5)
        groups[filename] = runs
        if marker:
            for run in runs[:3]:
                data = gh.metrics_for_run(run, marker, job)
                if data is not None:
                    summaries[run["id"]] = data
    board = render(
        gh.repo, groups, summaries, issue.get("body") or "",
        datetime.now(timezone.utc),
    )
    result = gh.upsert_comment(board)
    # Only status, not the user-facing body, is sent to job logs.
    print("INTERSECTION_OPS_STATUS", result)


if __name__ == "__main__":
    main()
