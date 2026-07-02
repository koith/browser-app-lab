from aios.plugin.app import AppManifest, OrgApp

from .agents import build_agents


class PublishingApp(OrgApp):
    manifest = AppManifest(
        name="publishing", version="0.1",
        task_types=("publishing.title_review",
                    "publishing.concept_pitch",
                    "publishing.cover_review"),
        description="AIOS 위에서 실행되는 출판사 조직")

    def __init__(self, llm, on_conclusion=None):
        self._llm = llm
        self._on_conclusion = on_conclusion  # 편집장 결재함 훅 (커널 밖 UI)

    def install(self, api):
        for agent in build_agents(api, self._llm):
            api.register_agent(agent)
        api.subscribe("meeting.concluded", self._to_editor_inbox)

    def _to_editor_inbox(self, ev):
        line = (f"[편집장 결재함] task={ev.payload['task_id']} "
                f"결론={str(ev.payload['conclusion'].get('decision'))[:80]}")
        if self._on_conclusion:
            self._on_conclusion(line)
        else:
            print(line)
