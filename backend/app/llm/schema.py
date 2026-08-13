from typing import List

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    title: str
    description: str = ""
    type: str = "learn"
    effort_hours: float = Field(default=1.0)


class MilestoneSpec(BaseModel):
    title: str
    description: str = ""
    order: int = 0
    tasks: List[TaskSpec]


class PlanSpec(BaseModel):
    strategy: str = ""
    milestones: List[MilestoneSpec]
