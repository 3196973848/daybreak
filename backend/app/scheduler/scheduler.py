import math
from dataclasses import dataclass
from datetime import date, timedelta

from ..llm.schema import PlanSpec


@dataclass
class ScheduledTask:
    milestone_index: int
    task_index: int
    date: date


def group_tasks(plan: PlanSpec, daily_hours: float) -> list[list[tuple[int, int]]]:
    groups: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    used = 0.0
    for milestone_index, milestone in enumerate(plan.milestones):
        for task_index, task in enumerate(milestone.tasks):
            if task.effort_hours > daily_hours:
                raise ValueError("单个任务耗时超过每日投入时间")
            if current and used + task.effort_hours > daily_hours + 1e-9:
                groups.append(current)
                current = []
                used = 0.0
            current.append((milestone_index, task_index))
            used += task.effort_hours
    if current:
        groups.append(current)
    return groups


def schedule(
    plan: PlanSpec,
    start_date: date,
    blocks_per_day: int = 2,
    hours_per_block: float = 1.0,
    end_date: date | None = None,
    daily_hours: float | None = None,
) -> list[ScheduledTask]:
    if end_date is not None:
        if end_date < start_date:
            raise ValueError("target_date 不能早于 start_date")
        if daily_hours is not None:
            groups = group_tasks(plan, daily_hours)
            if not groups:
                return []
            day_count = (end_date - start_date).days + 1
            if len(groups) > day_count:
                raise ValueError(
                    f"计划需要 {len(groups)} 个自然日，但截止日期前只有 {day_count} 个自然日"
                )
            if len(groups) == 1:
                group_dates = [start_date]
            else:
                group_dates = [
                    start_date + timedelta(
                        days=round(index * (day_count - 1) / (len(groups) - 1))
                    )
                    for index in range(len(groups))
                ]
            return [
                ScheduledTask(milestone_index, task_index, group_date)
                for group, group_date in zip(groups, group_dates)
                for milestone_index, task_index in group
            ]

        task_keys = [
            (milestone_index, task_index)
            for milestone_index, milestone in enumerate(plan.milestones)
            for task_index, _ in enumerate(milestone.tasks)
        ]
        if not task_keys:
            return []
        if len(task_keys) == 1:
            milestone_index, task_index = task_keys[0]
            return [ScheduledTask(milestone_index, task_index, start_date)]
        span_days = (end_date - start_date).days
        last_index = len(task_keys) - 1
        return [
            ScheduledTask(
                milestone_index,
                task_index,
                start_date + timedelta(days=round(index * span_days / last_index)),
            )
            for index, (milestone_index, task_index) in enumerate(task_keys)
        ]

    if blocks_per_day <= 0 or hours_per_block <= 0:
        raise ValueError("blocks_per_day 和 hours_per_block 必须为正数")
    out: list[ScheduledTask] = []
    day = start_date
    blocks_left = blocks_per_day
    for milestone_index, milestone in enumerate(plan.milestones):
        for task_index, task in enumerate(milestone.tasks):
            needed = max(1, math.ceil(task.effort_hours / hours_per_block))
            if needed > blocks_left:
                day += timedelta(days=1)
                blocks_left = blocks_per_day
            out.append(ScheduledTask(milestone_index, task_index, day))
            blocks_left = max(0, blocks_left - needed)
    return out
