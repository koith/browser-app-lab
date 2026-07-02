"""Storage(ABC) — 문서형 저장 계약. SQLite/JSON 어느 쪽이든 커널은 모른다."""
from __future__ import annotations

import dataclasses
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum


def to_jsonable(obj):
    """dataclass/Enum/datetime을 JSON 가능한 dict로 정규화. id가 없으면 발급."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        obj = dataclasses.asdict(obj)
    if isinstance(obj, dict):
        out = {k: to_jsonable(v) for k, v in obj.items()}
        if "id" not in out:
            out["id"] = uuid.uuid4().hex[:12]
        return out
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj


def matches(row: dict, filters: dict) -> bool:
    return all(row.get(k) == v for k, v in filters.items())


class Storage(ABC):
    @abstractmethod
    def save(self, kind: str, obj) -> dict: ...

    @abstractmethod
    def load(self, kind: str, obj_id: str) -> dict | None: ...

    @abstractmethod
    def query(self, kind: str, **filters) -> list[dict]: ...
