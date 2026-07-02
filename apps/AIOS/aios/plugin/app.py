"""Plugin SDK — App은 커널의 확장이 아니라 커널 위의 프로그램이다."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppManifest:
    name: str
    version: str
    task_types: tuple = field(default_factory=tuple)  # 소유 네임스페이스
    description: str = ""


class OrgApp(ABC):
    """모든 조직 App의 계약. KernelAPI 외에 커널을 만질 방법은 없다."""

    manifest: AppManifest

    @abstractmethod
    def install(self, api) -> None:
        """1) Agent 등록  2) 관심 이벤트 구독  3) App 고유 초기화"""

    def uninstall(self, api) -> None:  # 선택 구현
        pass


class AppLoader:
    def __init__(self, kernel):
        self._api = kernel.api()
        self._apps: dict[str, OrgApp] = {}

    def load(self, app: OrgApp) -> OrgApp:
        app.install(self._api)
        self._apps[app.manifest.name] = app
        return app

    def unload(self, name: str) -> None:
        app = self._apps.pop(name, None)
        if app:
            app.uninstall(self._api)
