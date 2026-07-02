from aios.kernel.agent import KPI, Agent, Goal, Name, PromptTemplate, Role


def build_agents(api, llm):
    spec = [
        ("게임 디렉터 AI", "재미의 최종 책임자",
         "당신은 게임 디렉터다. 핵심 재미(core loop) 관점에서 제안·결정하라."),
        ("레벨 디자인 AI", "플레이 경험을 공간으로 설계",
         "당신은 레벨 디자이너다. 난이도 곡선과 페이싱 관점에서 발언하라."),
        ("QA 비평 AI", "출시 전 모든 구멍을 찾는다",
         "당신은 QA 리드다. 엣지케이스·밸런스 붕괴 시나리오로 반박하라."),
        ("게임 시장조사 AI", "장르 트렌드 검증",
         "당신은 시장분석가다. 유사 장르 성과 데이터 관점에서 검증하라."),
    ]
    for name, goal, system in spec:
        yield Agent(
            name=Name(name),
            role=Role(title=name, capabilities=("game.*",)),
            goal=Goal(goal),
            kpi=KPI(),
            memory=api.make_memory(name),
            prompt=PromptTemplate(system=system),
            llm=llm)
