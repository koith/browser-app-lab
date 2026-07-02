"""Agent 8요소: Name / Role / Goal / KPI / Memory / Rules / Experience / Prompt.

Rules와 Experience는 소유하지 않고 Memory 계층(RuleMemory, ExperienceMemory)을
통해 조회한다 — 단일 진실 원천은 RuleEngine과 Storage다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Name:
    value: str


@dataclass(frozen=True)
class Role:
    title: str  # "기획 AI", "비평 AI"...
    capabilities: tuple = ()  # 처리 가능한 task_type 접두어. 예: ("publishing.*",)


@dataclass(frozen=True)
class Goal:
    statement: str


@dataclass
class KPI:
    metrics: dict = field(default_factory=dict)

    def record(self, metric: str, value: float) -> None:
        self.metrics[metric] = value

    def incr(self, metric: str, delta: float = 1.0) -> None:
        self.metrics[metric] = self.metrics.get(metric, 0.0) + delta


@dataclass(frozen=True)
class PromptTemplate:
    system: str

    def render(self, *, role, goal, rules, memories, context) -> str:
        rule_text = "\n".join(f"- {r}" for r in rules) or "- (없음)"
        mem_text = "\n".join(f"- {m}" for m in memories) or "- (없음)"
        return (f"{self.system}\n\n[역할] {role}\n[목표] {goal}\n"
                f"[조직 규칙 — 반드시 준수]\n{rule_text}\n"
                f"[관련 기억]\n{mem_text}\n\n[안건]\n{context}")


@dataclass
class Utterance:
    agent_name: str
    turn_type: str  # proposal | critique | rebuttal
    content: str


class Agent:
    """Agent는 스스로 움직이지 않는다. Orchestrator가 turn을 줄 때만 act()."""

    def __init__(self, name: Name, role: Role, goal: Goal, kpi: KPI,
                 memory, prompt: PromptTemplate, llm):
        self.name, self.role, self.goal, self.kpi = name, role, goal, kpi
        self.memory = memory      # Memory (4계층 파사드)
        self.prompt = prompt
        self._llm = llm           # LLMProvider — DI

    def act(self, turn_type: str, context: str) -> Utterance:
        bundle = self.memory.recall(context)  # 4계층 통합 회상
        rendered = self.prompt.render(
            role=self.role.title, goal=self.goal.statement,
            rules=bundle.rules, memories=bundle.snippets, context=context)
        text = self._llm.complete(system=f"You are {self.name.value}.",
                                  prompt=f"[{turn_type}] {rendered}")
        self.memory.short.add(f"({turn_type}) {text}")
        self.kpi.incr(f"turns_{turn_type}")
        return Utterance(self.name.value, turn_type, text)


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name.value] = agent

    def get(self, name: str) -> Agent | None:
        return self._agents.get(name)

    def find_by_capability(self, task_type: str) -> list[Agent]:
        out = []
        for a in self._agents.values():
            for cap in a.role.capabilities:
                if cap == task_type or (cap.endswith(".*")
                                        and task_type.startswith(cap[:-1])):
                    out.append(a)
                    break
        return out
