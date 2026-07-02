"""RuleEngine — Experience가 임계 횟수 반복되면 Rule로 승격.

Rule의 유일한 생성 경로. Agent도 App도 Rule을 직접 만들 수 없다.
편집장은 deactivate()라는 거부권을 가진다 — 인간이 조직 규범의 최종 결재자.
"""
from __future__ import annotations

import re
import uuid

from .bus import Event, Topics


class RuleEngine:
    def __init__(self, bus, storage, promote_threshold: int = 3):
        self._bus, self._s = bus, storage
        self._th = promote_threshold
        bus.subscribe(Topics.EXPERIENCE_SAVED, self._on_experience)

    def _on_experience(self, ev: Event) -> None:
        key = self._norm_key(ev.payload["lesson"])
        cand = self._s.load("rule_candidates", key) or {
            "id": key,
            "normalized_text": ev.payload["lesson"],
            "count": 0,
            "evidence": [],
            "scope": ev.payload["scope"],
        }
        cand["count"] += 1
        cand["evidence"].append(ev.payload["experience_id"])
        self._s.save("rule_candidates", cand)
        self._bus.publish(Event(
            Topics.RULE_CANDIDATE,
            {"text": cand["normalized_text"], "count": cand["count"],
             "threshold": self._th, "scope": cand["scope"]},
            correlation_id=ev.correlation_id))
        if cand["count"] >= self._th:
            self._promote(cand, ev.correlation_id)

    def _promote(self, cand: dict, corr: str) -> None:
        rule = {"id": uuid.uuid4().hex[:12],
                "text": cand["normalized_text"],
                "scope": cand["scope"],
                "origin": list(cand["evidence"]),
                "active": 1}
        self._s.save("rules", rule)
        cand["count"] = 0  # 재승격 방지 리셋
        self._s.save("rule_candidates", cand)
        self._bus.publish(Event(
            Topics.RULE_PROMOTED,
            {"rule_id": rule["id"], "text": rule["text"],
             "scope": rule["scope"]},
            correlation_id=corr))

    def rules_for(self, role_title: str) -> list[dict]:
        return [r for r in self._s.query("rules", active=1)
                if r["scope"] in (role_title, "org")]

    def deactivate(self, rule_id: str) -> None:
        """편집장의 거부권."""
        r = self._s.load("rules", rule_id)
        if r:
            r["active"] = 0
            self._s.save("rules", r)

    @staticmethod
    def _norm_key(text: str) -> str:
        return re.sub(r"\s+", "", text)[:64]
