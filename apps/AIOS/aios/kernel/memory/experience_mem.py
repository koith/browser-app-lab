"""ExperienceMemory — 조직 회고록. 쓰기 주체는 ExperienceEngine뿐."""
from .base import MemoryLayer


class ExperienceMemory(MemoryLayer):
    def __init__(self, agent_role: str, storage):
        self._role, self._s = agent_role, storage

    def add(self, content, **meta):
        raise PermissionError(
            "Experience는 ExperienceEngine(피드백/회고)으로만 생성된다")

    def recall(self, query, k=3):
        rows = (self._s.query("experiences", scope=self._role)
                + self._s.query("experiences", scope="org"))
        return [r["lesson"] for r in rows[-k:]]
