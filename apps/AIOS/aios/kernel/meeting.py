"""MeetingOrchestrator — 시스템콜 #3(회의)·#4(반론)·#5(결론).

회의 = 커널 스케줄러. 발언권을 배분하고 결론을 강제한다.
라운드: proposal → critique → rebuttal → (반복) → conclude
Agent는 서로를 모른다. 발언록(context)만 Orchestrator가 전달한다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .agent import Utterance
from .bus import Event, Topics


@dataclass
class Meeting:
    task_id: str
    participants: list
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    turns: list = field(default_factory=list)
    conclusion: dict | None = None


class MeetingOrchestrator:
    def __init__(self, bus, storage, policy, chair_llm, max_rounds: int = 2):
        self._bus, self._storage = bus, storage
        self._policy, self._chair = policy, chair_llm
        self._max_rounds = max_rounds

    def convene(self, task, agents) -> Meeting:
        m = Meeting(task_id=task.id,
                    participants=[a.name.value for a in agents])
        self._bus.publish(Event(
            Topics.MEETING_OPENED,
            {"meeting_id": m.id, "participants": m.participants},
            correlation_id=task.id))

        context = f"{task.title} — 목표: {task.goal}"
        proposer, critics = agents[0], (agents[1:] or agents[:1])

        for rnd in range(self._max_rounds):
            self._turn(m, proposer,
                       "proposal" if rnd == 0 else "rebuttal",
                       context, task.id)
            for c in critics:
                self._turn(m, c, "critique", self._transcript(m), task.id)
            context = self._transcript(m)

        m.conclusion = self._policy.conclude(m, self._chair)
        self._storage.save("meetings", m)
        self._bus.publish(Event(
            Topics.MEETING_CONCLUDED,
            {"meeting_id": m.id, "task_id": m.task_id,
             "participants": m.participants,
             "conclusion": m.conclusion, "turn_count": len(m.turns)},
            correlation_id=task.id))
        return m

    def _turn(self, m: Meeting, agent, turn_type: str, ctx: str, task_id: str):
        u: Utterance = agent.act(turn_type, ctx)
        m.turns.append(u)
        topic = {"proposal": Topics.TURN_PROPOSAL,
                 "critique": Topics.TURN_CRITIQUE,
                 "rebuttal": Topics.TURN_REBUTTAL}[turn_type]
        self._bus.publish(Event(
            topic,
            {"meeting_id": m.id, "agent": u.agent_name, "content": u.content},
            correlation_id=task_id))

    @staticmethod
    def _transcript(m: Meeting) -> str:
        return "\n".join(f"{u.agent_name}({u.turn_type}): {u.content}"
                         for u in m.turns)
