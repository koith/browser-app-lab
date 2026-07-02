"""ExperienceEngine — 시스템콜 #6 후반부(경험 저장).

Experience는 모델 학습이 아니다.
편집장(인간)의 피드백과 회고가 '조직의 교훈'으로 축적되는 파이프라인이다.
Rule 승격 판단은 하지 않는다(SRP) — 그것은 RuleEngine의 일이다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from .bus import Event, Topics


@dataclass(frozen=True)
class Feedback:
    task_id: str
    source: str  # "human:편집장" — 인간 출처를 명시적으로 기록
    text: str


@dataclass(frozen=True)
class Experience:
    id: str
    task_id: str
    lesson: str   # 정규화된 교훈 문장
    origin: str   # "feedback" | "retro"
    scope: str    # 대상 역할 제목 또는 "org"


def default_normalizer(text: str) -> tuple[str, str]:
    """v0.1: 사전 매핑 + 원문 유지. v0.2: LLM 의미 정규화 드라이버로 교체."""
    table = {
        "제목이 너무 길다": ("제목은 짧고 명확하게 유지한다", "기획 AI"),
        "근거가 부족하다": ("모든 제안에는 데이터 근거를 첨부한다", "org"),
    }
    return table.get(text.strip(), (f"교훈: {text.strip()}", "org"))


class ExperienceEngine:
    def __init__(self, bus, storage, normalizer=None):
        self._bus, self._s = bus, storage
        self._normalize = normalizer or default_normalizer
        bus.subscribe(Topics.FEEDBACK_RECEIVED, self._on_feedback)
        bus.subscribe(Topics.RETRO_COMPLETED, self._on_retro)

    def _on_feedback(self, ev: Event) -> None:
        fb = Feedback(ev.payload["task_id"], ev.payload["source"],
                      ev.payload["text"])
        self._s.save("feedback", fb)
        lesson, scope = self._normalize(fb.text)
        self._emit(fb.task_id, lesson, "feedback", scope)

    def _on_retro(self, ev: Event) -> None:
        for lesson in ev.payload.get("lessons", []):
            self._emit(ev.payload["task_id"], lesson, "retro", "org")

    def _emit(self, task_id: str, lesson: str, origin: str, scope: str) -> None:
        exp = Experience(uuid.uuid4().hex[:12], task_id, lesson, origin, scope)
        self._s.save("experiences", exp)
        self._bus.publish(Event(
            Topics.EXPERIENCE_SAVED,
            {"experience_id": exp.id, "task_id": task_id,
             "lesson": exp.lesson, "origin": origin, "scope": exp.scope},
            correlation_id=task_id))
