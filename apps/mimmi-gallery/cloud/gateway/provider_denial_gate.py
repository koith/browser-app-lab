"""Bounded fail-closed cooldown for explicit owner-storage provider denials.

Only suppress repeated reads of the SAME authorized remote after a known
access-control denial. Never transform the denial into access, retry through
another identity, or hide integrity errors. Verified memory-cache hits bypass
this gate because it is applied only before a fresh remote request.
"""
from __future__ import annotations

import re
import time
from typing import Callable


class ProviderAccessHeld(Exception):
    def __init__(self, retry_seconds: int):
        super().__init__("Provider access currently denied")
        self.retry_seconds = retry_seconds


class ProviderDenialGate:
    _DENIAL = re.compile(
        r"anti[\s-]*hotlinking|[\"']?error_code[\"']?\s*[:=]\s*31326",
        re.IGNORECASE,
    )

    def __init__(self, seconds: int = 25, now: Callable[[], float] | None = None):
        if not 1 <= seconds <= 120:
            raise ValueError("Provider denial cooldown must be bounded")
        self.seconds = seconds
        self.now = now or time.monotonic
        self.blocked_until: dict[str, float] = {}

    def guard(self, remote: str) -> None:
        remaining = self.blocked_until.get(remote, 0.0) - self.now()
        if remaining > 0:
            raise ProviderAccessHeld(max(1, int(remaining + 0.999)))

    def record(self, remote: str, error: str) -> bool:
        if not self._DENIAL.search(error):
            return False
        self.blocked_until[remote] = self.now() + self.seconds
        return True

    def success(self, remote: str) -> None:
        self.blocked_until.pop(remote, None)
