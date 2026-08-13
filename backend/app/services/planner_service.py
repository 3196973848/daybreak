import math
from datetime import date

from sqlalchemy.orm import Session

from ..config import settings
from ..llm.planner import generate_plan
from ..models import Goal, Milestone, Plan, Task
from ..scheduler.duration import DurationUnit, calculate_target_date
from ..scheduler.scheduler import group_tasks, schedule
from .capacity import InsufficientCapacityError
from .plan_validation import PlanValidationError, validate_atomic_plan


def create_goal_with_plan(
    db: Session,
    title: str,
    description: str = "",
    target_date: date | None = None,
    duration_value: int | None = None,
    duration_unit: DurationUnit | None = None,
    daily_hours: float = 2.0,
) -> Goal:
    start = date.today()
    try:
        if (duration_value is None) != (duration_unit is None):
            raise ValueError("duration_value 与 duration_unit 必须同时提供")
        if target_date is not None and duration_value is not None:
            raise ValueError("target_date 与预计完成时长不能同时提供")
        if duration_value is not None and duration_unit is not None:
            target_date = calculate_target_date(start, duration_value, duration_unit)
        if target_date is not None and target_date < start:
            raise ValueError("target_date 不能早于今天")

        feedback = None
        spec = None
        for attempt in range(3):
            spec = generate_plan(
                title,
                description,
                target_date.isoformat() if target_date else None,
                daily_hours=daily_hours,
                feedback=feedback,
            )
            try:
                validate_atomic_plan(spec, daily_hours)
                break
            except PlanValidationError as exc:
                feedback = f"{exc}；请确保单个任务不超过每日投入时间"
                if attempt == 2:
                    raise RuntimeError("无法生成有效的原子计划") from exc

        groups = group_tasks(spec, daily_hours)
        if target_date is not None:
            required_hours = sum(
                task.effort_hours
                for milestone in spec.milestones
                for task in milestone.tasks
            )
            day_count = (target_date - start).days + 1
            minimum_days = max(
                math.ceil(required_hours / daily_hours),
                len(groups),
            )
            if minimum_days > day_count:
                raise InsufficientCapacityError(
                    required_hours,
                    day_count * daily_hours,
                    minimum_days,
                )

        goal = Goal(title=title, description=description, target_date=target_date)
        db.add(goal)
        db.flush()
        scheduled = schedule(
            spec,
            start,
            blocks_per_day=settings.blocks_per_day,
            hours_per_block=settings.hours_per_block,
            end_date=target_date,
            daily_hours=daily_hours,
        )
        by_key = {(r.milestone_index, r.task_index): r.date for r in scheduled}
        dates_by_milestone = {
            milestone_index: [
                by_key[(milestone_index, task_index)]
                for task_index, _ in enumerate(ms.tasks)
            ]
            for milestone_index, ms in enumerate(spec.milestones)
        }

        plan = Plan(goal_id=goal.id, strategy=spec.strategy, status="active")
        db.add(plan)
        db.flush()
        previous_nonempty_due = start
        for mi, ms in enumerate(spec.milestones):
            milestone_dates = dates_by_milestone[mi]
            if milestone_dates:
                due = milestone_dates[-1]
                previous_nonempty_due = due
            else:
                due = previous_nonempty_due
            milestone = Milestone(
                plan_id=plan.id, title=ms.title, description=ms.description,
                order=ms.order, due_date=due, status="todo",
            )
            db.add(milestone)
            db.flush()
            for idx, t in enumerate(ms.tasks):
                db.add(Task(
                    milestone_id=milestone.id, title=t.title, description=t.description,
                    type=t.type, scheduled_date=by_key[(mi, idx)],
                    effort=t.effort_hours, order=idx, status="todo", verified=False,
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(goal)
    return goal
