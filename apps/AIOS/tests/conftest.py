import pytest

from aios.drivers.llm.mock import MockProvider
from aios.drivers.storage.json_store import JsonFileStorage
from aios.drivers.storage.sqlite_store import SQLiteStorage


@pytest.fixture(params=["sqlite", "json"])
def storage(request, tmp_path):
    """Liskov 검증: 두 저장소 구현에서 전 테스트 동일 통과."""
    if request.param == "sqlite":
        return SQLiteStorage(str(tmp_path / "aios.db"))
    return JsonFileStorage(str(tmp_path / "json"))


@pytest.fixture
def llm():
    return MockProvider()
