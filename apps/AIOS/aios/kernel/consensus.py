"""ConsensusPolicy — 결론 도출 전략. 새 회의 방식은 클래스 추가로 확장(OCP)."""
from abc import ABC, abstractmethod


class ConsensusPolicy(ABC):
    @abstractmethod
    def conclude(self, meeting, chair_llm) -> dict: ...


class ChairDecides(ConsensusPolicy):
    """v0.1 기본: 전체 발언록을 의장 LLM이 요약·결정."""

    def conclude(self, meeting, chair_llm) -> dict:
        transcript = "\n".join(
            f"[{u.turn_type}] {u.agent_name}: {u.content}" for u in meeting.turns)
        text = chair_llm.complete(
            system="당신은 회의 의장이다. 결론/근거/기각된 대안을 정리하라.",
            prompt=transcript)
        return {"decision": text, "policy": "chair_decides"}

# class MajorityVote(ConsensusPolicy): ...   # 확장 지점
