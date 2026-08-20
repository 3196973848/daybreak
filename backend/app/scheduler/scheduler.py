import math
from dataclasses import dataclass
from datetime import date, timedelta

from ..llm.schema import PlanSpec


@dataclass
class ScheduledTask:
    milestone_index: int
    task_index: int
    date: date


def _next_work_day(day: date, rest_days: set[int], skip_dates: set[date] | None = None) -> date:
    """Find the next non-rest day starting from `day`."""
    _skip = skip_dates or set()
    while day.weekday() in rest_days or day in _skip:
        day += timedelta(days=1)
    return day


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
    rest_days: set[int] | None = None,
    skip_dates: set[date] | None = None,
) -> list[ScheduledTask]:
    """
    Schedule tasks into days.
    rest_days: set of weekday numbers (0=Monday, 6=Sunday) to skip.
    skip_dates: set of specific dates to skip (e.g., leave dates).
    """
    _rest = rest_days or set()
    _skip = skip_dates or set()

    if end_date is not None:
        if end_date < start_date:
            raise ValueError("target_date 不能早于 start_date")
        if daily_hours is not None:
            groups = group_tasks(plan, daily_hours)
            if not groups:
                return []
            # Count available working days between start and end
            working_days = []
            d = start_date
            while d <= end_date:
                if d.weekday() not in _rest and d not in _skip:
                    working_days.append(d)
                d += timedelta(days=1)
            if len(groups) > len(working_days):
                raise ValueError(
                    f"计划需要 {len(groups)} 个工作日，但截止日期前只有 {len(working_days)} 个工作日"
                )
            # Pack groups into consecutive working days (fill each day)
            group_dates = working_days[:len(groups)]
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
        # Pack tasks into consecutive working days
        working_days = []
        d = _next_work_day(start_date, _rest)
        while d <= end_date:
            if d.weekday() not in _rest:
                working_days.append(d)
            d += timedelta(days=1)
        if not working_days:
            return []
        # Each task gets its own day, filling consecutively
        return [
            ScheduledTask(
                milestone_index,
                task_index,
                working_days[min(index, len(working_days) - 1)],
            )
            for index, (milestone_index, task_index) in enumerate(task_keys)
        ]

    # No end_date: pack tasks into working days, filling each day to daily_hours
    _dh = daily_hours or (blocks_per_day * hours_per_block)
    if blocks_per_day <= 0 or hours_per_block <= 0:
        raise ValueError("blocks_per_day 和 hours_per_block 必须为正数")
    out: list[ScheduledTask] = []
    day = _next_work_day(start_date, _rest, _skip)
    hours_left = _dh
    for milestone_index, milestone in enumerate(plan.milestones):
        for task_index, task in enumerate(milestone.tasks):
            needed = task.effort_hours
            if needed > hours_left + 1e-9:
                day = _next_work_day(day + timedelta(days=1), _rest, _skip)
                hours_left = _dh
            out.append(ScheduledTask(milestone_index, task_index, day))
            hours_left = max(0, hours_left - needed)
    return out
