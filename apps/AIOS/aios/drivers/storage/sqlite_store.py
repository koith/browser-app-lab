"""SQLiteStorage — kind별 문서 테이블 (id, data JSON, created_at)."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .base import Storage, matches, to_jsonable


class SQLiteStorage(Storage):
    def __init__(self, path: str = "data/aios.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._tables: set[str] = set()

    def _table(self, kind: str) -> str:
        name = re.sub(r"[^a-zA-Z0-9_]", "_", kind)
        if name not in self._tables:
            self._db.execute(
                f"CREATE TABLE IF NOT EXISTS {name} ("
                "id TEXT PRIMARY KEY, data TEXT, created_at TEXT)")
            self._db.commit()
            self._tables.add(name)
        return name

    def save(self, kind: str, obj) -> dict:
        row = to_jsonable(obj)
        t = self._table(kind)
        self._db.execute(
            f"INSERT INTO {t}(id, data, created_at) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
            (row["id"], json.dumps(row, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat()))
        self._db.commit()
        return row

    def load(self, kind: str, obj_id: str) -> dict | None:
        t = self._table(kind)
        cur = self._db.execute(f"SELECT data FROM {t} WHERE id=?", (obj_id,))
        r = cur.fetchone()
        return json.loads(r[0]) if r else None

    def query(self, kind: str, **filters) -> list[dict]:
        t = self._table(kind)
        rows = [json.loads(r[0]) for r in
                self._db.execute(
                    f"SELECT data FROM {t} ORDER BY created_at").fetchall()]
        return [r for r in rows if matches(r, filters)]

    def close(self) -> None:
        self._db.close()
