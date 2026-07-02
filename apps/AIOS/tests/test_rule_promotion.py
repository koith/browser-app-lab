"""DoD #2·#3: 동일 피드백 3회 → Rule 승격 → 다음 회의 프롬프트에 주입."""
from aios.apps.gamestudio.manifest import GameStudioApp
from aios.apps.publishing.manifest import PublishingApp
from aios.kernel.kernel import Kernel
from aios.plugin.app import AppLoader


def boot(storage, llm):
    kernel = Kernel(storage=storage, llm=llm)
    loader = AppLoader(kernel)
    loader.load(PublishingApp(llm, on_conclusion=lambda _: None))
    loader.load(GameStudioApp(llm))
    return kernel


def test_feedback_repeated_promotes_rule(storage, llm):
    kernel = boot(storage, llm)
    api = kernel.api()
    task = api.create_task("제목 검토", "제목 결정", "publishing.title_review")

    for i in range(3):
        api.submit_feedback(task.id, "human:편집장", "제목이 너무 길다")
        rules = kernel.rules.rules_for("기획 AI")
        if i < 2:
            assert not any("제목은 짧고" in r["text"] for r in rules)
    rules = kernel.rules.rules_for("기획 AI")
    assert any(r["text"] == "제목은 짧고 명확하게 유지한다" for r in rules)

    # DoD #3: 승격 직후 새 Task에서 기획 AI 프롬프트에 Rule 주입
    llm.calls.clear()
    api.create_task("후속작 피칭", "방향 결정", "publishing.concept_pitch")
    proposals = [c for c in llm.calls if "[proposal]" in c["prompt"]]
    assert proposals and "제목은 짧고 명확하게 유지한다" in proposals[0]["prompt"]

    # Rule 격리: 게임 스튜디오 회의에는 출판 Rule이 새지 않는다
    llm.calls.clear()
    api.create_task("컨셉 리뷰", "코어 루프", "game.concept_review")
    game_prompts = [c["prompt"] for c in llm.calls if "[proposal]" in c["prompt"]]
    assert game_prompts and "제목은 짧고" not in game_prompts[0]


def test_editor_veto_deactivates_rule(storage, llm):
    kernel = boot(storage, llm)
    api = kernel.api()
    t = api.create_task("제목 검토", "제목 결정", "publishing.title_review")
    for _ in range(3):
        api.submit_feedback(t.id, "human:편집장", "제목이 너무 길다")
    rule = next(r for r in kernel.rules.rules_for("기획 AI")
                if "제목은 짧고" in r["text"])
    kernel.rules.deactivate(rule["id"])
    assert not any("제목은 짧고" in r["text"]
                   for r in kernel.rules.rules_for("기획 AI"))


def test_rule_memory_is_read_only(storage, llm):
    import pytest
    kernel = boot(storage, llm)
    agent = kernel.registry.get("기획 AI")
    with pytest.raises(PermissionError):
        agent.memory.rule.add("몰래 규칙 넣기")
