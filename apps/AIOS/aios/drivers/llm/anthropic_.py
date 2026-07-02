"""실제 LLM 드라이버 (선택). `pip install anthropic` 필요.

커널 인터페이스는 MockProvider와 완전히 동일하다(LSP).
"""
from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 800):
        try:
            import anthropic  # noqa: PLC0415
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "anthropic 패키지가 없습니다: pip install anthropic") from e
        self._client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용
        self._model, self._max = model, max_tokens

    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover
        msg = self._client.messages.create(
            model=self._model, max_tokens=self._max, system=system,
            messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in msg.content if b.type == "text")
