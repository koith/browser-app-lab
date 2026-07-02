"""LongTermMemory — 영속 개인 기억 (업무노트). 회고 후 consolidate로 적재."""
from .base import MemoryLayer


class LongTermMemory(MemoryLayer):
    def __init__(self, agent: str, storage):
        self._a, self._s = agent, storage

    def add(self, content, importance=0.5, **meta):
        self._s.save("memories", {"agent": self._a, "layer": "long",
                                  "content": content,
                                  "importance": importance})

    def recall(self, query, k=5):
        rows = self._s.query("memories", agent=self._a, layer="long")
        scored = sorted(rows, key=lambda r: self._score(query, r), reverse=True)
        return [r["content"] for r in scored[:k]]

    @staticmethod
    def _score(q, row):
        # v0.1: 키워드 겹침. v0.2: 임베딩 드라이버로 교체 지점.
        qs = set(q.split())
        return len(qs & set(str(row.get("content", "")).split()))
