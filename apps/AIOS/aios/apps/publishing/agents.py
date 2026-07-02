from aios.kernel.agent import KPI, Agent, Goal, Name, PromptTemplate, Role


def build_agents(api, llm):
    spec = [
        ("기획 AI", "독자가 집어 들 기획을 만든다",
         "당신은 출판 기획자다. 제목/컨셉/타깃을 제안하라.",
         {"proposal_accept_rate": 0.0}),
        ("비평 AI", "약한 기획을 통과시키지 않는다",
         "당신은 냉정한 편집 비평가다. 논리·시장성 허점을 지적하라.",
         {"valid_critique_rate": 0.0}),
        ("시장조사 AI", "데이터 없는 직감을 걸러낸다",
         "당신은 시장분석가다. 경쟁서·트렌드 관점에서 검증하라.",
         {"evidence_per_meeting": 0.0}),
    ]
    for name, goal, system, kpi in spec:
        yield Agent(
            name=Name(name),
            role=Role(title=name, capabilities=("publishing.*",)),
            goal=Goal(goal),
            kpi=KPI(dict(kpi)),
            memory=api.make_memory(name),   # 커널이 4계층 메모리 발급
            prompt=PromptTemplate(system=system),
            llm=llm)
