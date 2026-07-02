"""JsonFileStorage — data/json/{kind}/{id}.json. 데모에서 상태를 눈으로 확인."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .base import Storage, matches, to_jsonable


class JsonFileStorage(Storage):
    def __init__(self, root: str = "data/json"):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def _dir(self, kind: str) -> Path:
        d = self._root / re.sub(r"[^a-zA-Z0-9_.-]", "_", kind)
        d.mkdir(exist_ok=True)
        return d

    def save(self, kind: str, obj) -> dict:
        row = to_jsonable(obj)
        self._seq += 1
        row.setdefault("_seq", self._seq)          # 삽입 순서 보존
        row.setdefault("_ts", time.time())
        (self._dir(kind) / f"{row['id']}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        return row

    def load(self, kind: str, obj_id: str):
        p = self._dir(kind) / f"{obj_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def query(self, kind: str, **filters) -> list:
        rows = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(self._dir(kind).glob("*.json"))]
        rows.sort(key=lambda r: r.get("_seq", 0))
        return [r for r in rows if matches(r, filters)]
