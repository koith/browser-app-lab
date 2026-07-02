"""MessageBus — AIOS의 신경계. 모든 모듈/Agent는 오직 여기로만 대화한다."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True)
class Event:
    topic: str
    payload: dict
    correlation_id: str  # 보통 task_id — 하나의 Task 흐름 추적
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Topics:
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    MEETING_OPENED = "meeting.opened"
    TURN_PROPOSAL = "meeting.turn.proposal"
    TURN_CRITIQUE = "meeting.turn.critique"
    TURN_REBUTTAL = "meeting.turn.rebuttal"
    MEETING_CONCLUDED = "meeting.concluded"
    RETRO_COMPLETED = "retro.completed"
    FEEDBACK_RECEIVED = "feedback.received"
    EXPERIENCE_SAVED = "experience.saved"
    RULE_CANDIDATE = "rule.candidate.created"
    RULE_PROMOTED = "rule.promoted"


Handler = Callable[[Event], None]


class MessageBus:
    """동기식 pub/sub. 와일드카드 'task.*' 및 전체 구독 '*' 지원.

    v0.2에서 asyncio 큐/원격 브로커로 교체하더라도 이 인터페이스는 불변이다.
    """

    def __init__(self, storage=None):
        self._subs: dict[str, list[Handler]] = {}
        self._storage = storage  # 이벤트 로그 영속화 (감사/재생용)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs.setdefault(topic, []).append(handler)

    def publish(self, event: Event) -> None:
        if self._storage is not None:
            self._storage.save("events", event)
        for pattern, handlers in list(self._subs.items()):
            if self._match(pattern, event.topic):
                for h in list(handlers):
                    h(event)

    @staticmethod
    def _match(pattern: str, topic: str) -> bool:
        if pattern == "*" or pattern == topic:
            return True
        return pattern.endswith(".*") and topic.startswith(pattern[:-1])
