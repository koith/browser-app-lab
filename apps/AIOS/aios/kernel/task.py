"""Task — AIOS의 프로세스. 시스템콜 #1."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from .bus import Event, Topics


class TaskState(str, Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_MEETING = "in_meeting"
    CONCLUDED = "concluded"
    RETROSPECTED = "retrospected"
    ARCHIVED = "archived"


@dataclass
class Task:
    title: str
    goal: str
    task_type: str  # 예: "publishing.title_review"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: TaskState = TaskState.CREATED
    conclusion: dict | None = None


class TaskManager:
    """상태전이의 유일한 관문."""

    _LEGAL = {
        TaskState.CREATED: {TaskState.ASSIGNED},
        TaskState.ASSIGNED: {TaskState.IN_MEETING},
        TaskState.IN_MEETING: {TaskState.CONCLUDED},
        TaskState.CONCLUDED: {TaskState.RETROSPECTED},
        TaskState.RETROSPECTED: {TaskState.ARCHIVED},
    }

    def __init__(self, bus, storage):
        self._bus, self._storage = bus, storage
        self._tasks: dict[str, Task] = {}

    def create(self, title: str, goal: str, task_type: str) -> Task:
        task = Task(title=title, goal=goal, task_type=task_type)
        self._tasks[task.id] = task
        self._storage.save("tasks", task)
        self._bus.publish(Event(
            Topics.TASK_CREATED,
            {"task_id": task.id, "task_type": task_type,
             "title": title, "goal": goal},
            correlation_id=task.id))
        return task

    def get(self, task_id: str) -> Task:
        return self._tasks[task_id]

    def transition(self, task_id: str, to: TaskState) -> None:
        task = self._tasks[task_id]
        if to not in self._LEGAL[task.state]:
            raise ValueError(f"illegal transition {task.state} -> {to}")
        task.state = to
        self._storage.save("tasks", task)
