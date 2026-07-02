"""Kernel — Composition Root. 모든 의존성 주입은 여기서만 일어난다.

커널 내부 모듈들조차 서로 직접 호출하지 않고 Bus로만 연결된다.
"""
from __future__ import annotations

from .agent import AgentRegistry
from .bus import Event, MessageBus, Topics
from .consensus import ChairDecides
from .experience import ExperienceEngine
from .meeting import MeetingOrchestrator
from .memory import Memory
from .retrospective import RetrospectiveService
from .rules import RuleEngine
from .selector import CapabilitySelector
from .task import TaskManager, TaskState


class Kernel:
    def __init__(self, storage, llm, selector=None, policy=None,
                 promote_threshold: int = 3, max_rounds: int = 2):
        self.storage, self.llm = storage, llm
        self.bus = MessageBus(storage)
        self.tasks = TaskManager(self.bus, storage)
        self.registry = AgentRegistry()
        self.selector = selector or CapabilitySelector()
        self.meetings = MeetingOrchestrator(
            self.bus, storage, policy or ChairDecides(), llm,
            max_rounds=max_rounds)
        self.retro = RetrospectiveService(self.bus, storage, llm)
        self.experience = ExperienceEngine(self.bus, storage)
        self.rules = RuleEngine(self.bus, storage,
                                promote_threshold=promote_threshold)
        self._wire()

    # -- 커널 내부 배선: 이벤트 → 다음 단계 --------------------------------
    def _wire(self) -> None:
        self.bus.subscribe(Topics.TASK_CREATED, self._on_task_created)
        self.bus.subscribe(Topics.MEETING_CONCLUDED, self._on_meeting_concluded)
        self.bus.subscribe(Topics.RETRO_COMPLETED, self._on_retro_completed)

    def _on_task_created(self, ev: Event) -> None:
        task = self.tasks.get(ev.payload["task_id"])
        candidates = self.registry.find_by_capability(task.task_type)
        agents = self.selector.select(task, candidates)
        self.tasks.transition(task.id, TaskState.ASSIGNED)
        self.bus.publish(Event(
            Topics.TASK_ASSIGNED,
            {"task_id": task.id, "agents": [a.name.value for a in agents]},
            correlation_id=task.id))
        self.tasks.transition(task.id, TaskState.IN_MEETING)
        meeting = self.meetings.convene(task, agents)
        task.conclusion = meeting.conclusion
        self.storage.save("tasks", task)

    def _on_meeting_concluded(self, ev: Event) -> None:
        self.tasks.transition(ev.payload["task_id"], TaskState.CONCLUDED)
        self.retro.run(ev.payload)  # → retro.completed 발행
        # 기억 정리: Short → Long 승격 후 초기화
        for name in ev.payload.get("participants", []):
            agent = self.registry.get(name)
            if agent is not None:
                agent.memory.consolidate()

    def _on_retro_completed(self, ev: Event) -> None:
        task = self.tasks.get(ev.payload["task_id"])
        if task.state == TaskState.CONCLUDED:
            self.tasks.transition(task.id, TaskState.RETROSPECTED)

    def api(self) -> "KernelAPI":
        return KernelAPI(self)

    def shutdown(self) -> None:
        close = getattr(self.storage, "close", None)
        if close:
            close()


class KernelAPI:
    """App(사용자 공간)에 노출되는 유일한 표면 = 시스템콜."""

    def __init__(self, kernel: Kernel):
        self._k = kernel

    def create_task(self, title: str, goal: str, task_type: str):
        return self._k.tasks.create(title, goal, task_type)

    def register_agent(self, agent) -> None:
        self._k.registry.register(agent)

    def submit_feedback(self, task_id: str, source: str, text: str) -> None:
        self._k.bus.publish(Event(
            Topics.FEEDBACK_RECEIVED,
            {"task_id": task_id, "source": source, "text": text},
            correlation_id=task_id))

    def subscribe(self, topic: str, handler) -> None:
        self._k.bus.subscribe(topic, handler)

    def make_memory(self, agent_name: str, role_title: str | None = None):
        """Agent 생성 시 4계층 메모리 발급."""
        return Memory(agent_name, self._k.storage, self._k.rules,
                      role_title=role_title)

    def rules(self, role_title: str) -> list:
        return self._k.rules.rules_for(role_title)
