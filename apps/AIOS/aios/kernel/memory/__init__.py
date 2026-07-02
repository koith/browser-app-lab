"""4계층 Memory 파사드.

recall 우선순위: ① Rule(반드시 준수) ② Experience(조직 교훈)
                 ③ Long(개인 장기기억) ④ Short(이번 회의 발언)
"""
from .base import MemoryBundle, MemoryLayer
from .short import ShortTermMemory
from .long import LongTermMemory
from .rule_mem import RuleMemory
from .experience_mem import ExperienceMemory

__all__ = ["Memory", "MemoryBundle", "MemoryLayer", "ShortTermMemory",
           "LongTermMemory", "RuleMemory", "ExperienceMemory"]


class Memory:
    def __init__(self, agent_name, storage, rule_engine, role_title=None):
        role = role_title or agent_name
        self.short = ShortTermMemory()
        self.long = LongTermMemory(agent_name, storage)
        self.rule = RuleMemory(role, rule_engine)
        self.experience = ExperienceMemory(role, storage)

    def recall(self, query: str) -> MemoryBundle:
        return MemoryBundle(
            rules=self.rule.recall(query),
            snippets=(self.experience.recall(query, 3)
                      + self.long.recall(query, 3)
                      + self.short.recall(query, 5)))

    def consolidate(self, summarizer=None) -> None:
        """회고 후: Short → Long 승격(요약), Short 비움."""
        items = self.short.flush()
        if items:
            summary = summarizer(items) if summarizer else " / ".join(items[-5:])
            self.long.add(f"[회의요약] {summary}", importance=0.7)
