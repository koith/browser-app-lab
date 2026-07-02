"""AIOS Kernel v0.1 데모.

6단계 E2E: Task 생성 → Agent 선택 → 회의 → 반론/토론 → 결론 → 회고/경험 저장,
그리고 편집장 피드백 3회 반복 → Rule 승격 → 다음 회의 프롬프트 자동 주입.
"""
from aios.apps.gamestudio.manifest import GameStudioApp
from aios.apps.publishing.manifest import PublishingApp
from aios.drivers.llm.mock import MockProvider
from aios.drivers.storage.sqlite_store import SQLiteStorage
from aios.kernel.kernel import Kernel
from aios.plugin.app import AppLoader

llm = MockProvider()
kernel = Kernel(storage=SQLiteStorage("data/aios.db"), llm=llm)
kernel.api().subscribe("*", lambda ev: print(f"  [bus] {ev.topic}"))

loader = AppLoader(kernel)
loader.load(PublishingApp(llm))
loader.load(GameStudioApp(llm))
api = kernel.api()

print("\n=== ① 출판사 Task: 회의 자동 진행 ===")
task = api.create_task(
    title="신간 『느리게 읽는 법』 제목 후보 검토",
    goal="타깃 독자에게 소구하는 최종 제목 방향 결정",
    task_type="publishing.title_review")
print(f"task 최종 상태: {task.state.value}")

print("\n=== ② 편집장 피드백 3회 → Rule 승격 ===")
for _ in range(3):
    api.submit_feedback(task.id, "human:편집장", "제목이 너무 길다")
for r in kernel.rules.rules_for("기획 AI"):
    print(f"  승격된 Rule[{r['scope']}]: {r['text']}")

print("\n=== ③ 다음 출판 회의: 기획 AI 프롬프트에 Rule 자동 주입 ===")
api.create_task("후속작 컨셉 피칭", "차기작 방향 결정",
                "publishing.concept_pitch")
injected = any("제목은 짧고 명확하게" in c["prompt"] for c in llm.calls[-12:])
print(f"  Rule 주입 확인: {injected}")

print("\n=== ④ 같은 커널 위의 게임 스튜디오 (커널 수정 0줄) ===")
g = api.create_task("신작 로그라이크 컨셉 리뷰", "코어 루프 확정",
                    "game.concept_review")
print(f"game task 최종 상태: {g.state.value}")

kernel.shutdown()
