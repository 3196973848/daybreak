from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    type: Literal["learn", "practice", "project"] = "learn"
    effort_hours: float = Field(default=1.0)


class MilestoneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    order: int = 0
    tasks: List[TaskSpec]


class PlanSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str = ""
    milestones: List[MilestoneSpec]
