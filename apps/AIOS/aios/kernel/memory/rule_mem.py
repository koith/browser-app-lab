"""RuleMemory — 소유하지 않는 읽기전용 '뷰'. 진실 원천은 RuleEngine.

rule.promoted 즉시 모든 Agent에 반영되는 이유가 이 구조다:
복사본이 없으므로 동기화 문제 자체가 존재하지 않는다.
"""
from .base import MemoryLayer


class RuleMemory(MemoryLayer):
    def __init__(self, agent_role: str, rule_engine):
        self._role, self._re = agent_role, rule_engine

    def add(self, *a, **k):
        raise PermissionError("Rule은 RuleEngine 승격으로만 생성된다")

    def recall(self, query, k=10):
        return [r["text"] for r in self._re.rules_for(self._role)][:k]
