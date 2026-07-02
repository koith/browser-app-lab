"""ShortTermMemory — 회의 1건 수명의 휘발성 기억 (RAM)."""
from collections import deque

from .base import MemoryLayer


class ShortTermMemory(MemoryLayer):
    def __init__(self, maxlen: int = 30):
        self._buf = deque(maxlen=maxlen)

    def add(self, content, **meta):
        self._buf.append(content)

    def recall(self, query, k=5):
        return list(self._buf)[-k:]

    def flush(self) -> list:
        items = list(self._buf)
        self._buf.clear()
        return items
