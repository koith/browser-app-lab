from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM은 드라이버다. 커널은 어떤 모델인지 모른다."""

    @abstractmethod
    def complete(self, system: str, prompt: str) -> str: ...
