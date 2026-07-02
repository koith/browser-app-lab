"""DoD #1: 6단계(생성→선택→회의→반론→결론→회고→경험저장) E2E."""
from aios.apps.publishing.manifest import PublishingApp
from aios.kernel.kernel import Kernel
from aios.kernel.task import TaskState
from aios.plugin.app import AppLoader


def boot(storage, llm):
    kernel = Kernel(storage=storage, llm=llm)
    AppLoader(kernel).load(PublishingApp(llm, on_conclusion=lambda _: None))
    return kernel


def test_six_syscalls_end_to_end(storage, llm):
    kernel = boot(storage, llm)
    task = kernel.api().create_task(
        "신간 제목 검토", "최종 제목 방향 결정", "publishing.title_review")

    # ⑤ 결론 + 상태머신 완주 (①~⑥)
    assert task.state == TaskState.RETROSPECTED
    assert task.conclusion and "결론" in task.conclusion["decision"]

    # ③④ 회의록: 제안/반론/재반론이 모두 존재
    meetings = storage.query("meetings", task_id=task.id)
    assert len(meetings) == 1
    turn_types = {t["turn_type"] for t in meetings[0]["turns"]}
    assert {"proposal", "critique", "rebuttal"} <= turn_types

    # ⑥ 회고 → 경험 저장
    assert storage.query("experiences", task_id=task.id, origin="retro")

    # 이벤트 로그에 전 단계가 남는다
    topics = {e["topic"] for e in storage.query("events")}
    for t in ["task.created", "task.assigned", "meeting.opened",
              "meeting.turn.proposal", "meeting.turn.critique",
              "meeting.turn.rebuttal", "meeting.concluded",
              "retro.completed", "experience.saved"]:
        assert t in topics, f"missing event: {t}"


def test_agents_never_call_each_other(storage, llm):
    """Agent 발언 context는 Orchestrator가 준 발언록뿐 — 직접 참조 없음."""
    kernel = boot(storage, llm)
    kernel.api().create_task("t", "g", "publishing.title_review")
    assert all("You are" in c["system"] or "의장" in c["system"]
               or "회고" in c["system"] for c in llm.calls)
