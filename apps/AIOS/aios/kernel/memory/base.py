from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MemoryBundle:
    rules: list = field(default_factory=list)
    snippets: list = field(default_factory=list)


class MemoryLayer(ABC):
    @abstractmethod
    def add(self, content: str, **meta) -> None: ...

    @abstractmethod
    def recall(self, query: str, k: int = 5) -> list: ...
