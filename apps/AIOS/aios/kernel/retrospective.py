"""RetrospectiveService — 시스템콜 #6 전반부(회고)."""
from .bus import Event, Topics


class RetrospectiveService:
    """meeting.concluded → 결론/과정에서 교훈 추출 → retro.completed"""

    def __init__(self, bus, storage, llm):
        self._bus, self._s, self._llm = bus, storage, llm

    def run(self, meeting_payload: dict) -> None:
        text = self._llm.complete(
            system=("당신은 회고 진행자다. 회의 결론과 과정을 보고 "
                    "'다음에도 반복할 것/하지 말 것'을 한 줄 교훈 목록으로 추출하라."),
            prompt=str(meeting_payload.get("conclusion")))
        lessons = [ln.strip("- ").strip()
                   for ln in text.splitlines() if ln.strip()]
        self._bus.publish(Event(
            Topics.RETRO_COMPLETED,
            {"task_id": meeting_payload["task_id"],
             "meeting_id": meeting_payload.get("meeting_id"),
             "lessons": lessons[:5]},
            correlation_id=meeting_payload["task_id"]))
