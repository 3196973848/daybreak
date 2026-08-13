import math
from dataclasses import dataclass
from datetime import date, timedelta

from ..llm.schema import PlanSpec


@dataclass
class ScheduledTask:
    milestone_index: int
    task_index: int
    date: date


def schedule(
    plan: PlanSpec,
    start_date: date,
    blocks_per_day: int = 2,
    hours_per_block: float = 1.0,
) -> list[ScheduledTask]:
    if blocks_per_day <= 0 or hours_per_block <= 0:
        raise ValueError("blocks_per_day 与 hours_per_block 必须为正数")
    out: list[ScheduledTask] = []
    day = start_date
    blocks_left = blocks_per_day
    for mi, ms in enumerate(plan.milestones):
        for idx, task in enumerate(ms.tasks):
            needed = max(1, math.ceil(task.effort_hours / hours_per_block))
            if needed > blocks_left:
                day += timedelta(days=1)
                blocks_left = blocks_per_day
            out.append(ScheduledTask(mi, idx, day))
            blocks_left = max(0, blocks_left - needed)
    return out

