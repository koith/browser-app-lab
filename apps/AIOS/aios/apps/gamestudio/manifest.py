from aios.plugin.app import AppManifest, OrgApp

from .agents import build_agents


class GameStudioApp(OrgApp):
    manifest = AppManifest(
        name="gamestudio", version="0.1",
        task_types=("game.concept_review",
                    "game.level_design_review",
                    "game.balance_review"),
        description="같은 커널, 같은 SDK, 다른 조직 — 커널 수정 0줄")

    def __init__(self, llm):
        self._llm = llm

    def install(self, api):
        for agent in build_agents(api, self._llm):
            api.register_agent(agent)
