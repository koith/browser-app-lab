"""MockProvider — 결정적 응답. 네트워크 0회로 커널 전체를 검증한다."""
from .base import LLMProvider


class MockProvider(LLMProvider):
    def __init__(self):
        self.calls: list[dict] = []  # 테스트에서 프롬프트 주입 검증용

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append({"system": system, "prompt": prompt})
        # 화자 판별은 system 우선 — 발언록(prompt) 안의 turn 마커에 속지 않는다
        if "의장" in system:
            return "결론: A안 채택. 근거: 토론 결과 핵심 반론이 해소됨."
        if "회고" in system:
            return "- 근거 데이터를 회의 전에 준비한다"
        if "[proposal]" in prompt:
            return "제안: A안을 추천한다. 근거: 타깃 독자 적합성."
        if "[critique]" in prompt:
            return "반론: 근거 데이터가 부족하다."
        if "[rebuttal]" in prompt:
            return "재반론: 보조 데이터 B로 보완 가능하다."
        return "의견: 특이사항 없음."
