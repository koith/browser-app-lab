"""AgentSelector — 시스템콜 #2. 전략 패턴 확장 지점."""
from abc import ABC, abstractmethod


class AgentSelector(ABC):
    @abstractmethod
    def select(self, task, candidates: list) -> list: ...


class CapabilitySelector(AgentSelector):
    """v0.1 기본: capability 매칭 결과에서 상한만 적용."""

    def __init__(self, max_agents: int = 5):
        self._max = max_agents

    def select(self, task, candidates):
        if not candidates:
            raise LookupError(f"no agent for task_type={task.task_type}")
        return candidates[: self._max]

# 확장 예 (커널 수정 없이 클래스만 추가):
# class KPISelector(AgentSelector): ...      # 성과 좋은 Agent 우선
# class AuctionSelector(AgentSelector): ...  # Agent가 입찰
