from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..llm.planner import generate_plan
from ..models import Goal, Milestone, Plan, Task
from ..scheduler.duration import DurationUnit, calculate_target_date
from ..scheduler.scheduler import schedule


def create_goal_with_plan(
    db: Session,
    title: str,
    description: str = "",
    target_date: date | None = None,
    duration_value: int | None = None,
    duration_unit: DurationUnit | None = None,
) -> Goal:
    start = date.today()
    if (duration_value is None) != (duration_unit is None):
        raise ValueError("duration_value 与 duration_unit 必须同时提供")
    if target_date is not None and duration_value is not None:
        raise ValueError("target_date 与预计完成时长不能同时提供")
    if duration_value is not None and duration_unit is not None:
        target_date = calculate_target_date(start, duration_value, duration_unit)
    if target_date is not None and target_date < start:
        raise ValueError("target_date 不能早于今天")

    try:
        goal = Goal(title=title, description=description, target_date=target_date)
        db.add(goal)
        db.flush()
        spec = generate_plan(title, description, target_date.isoformat() if target_date else None)
        scheduled = schedule(
            spec,
            start,
            blocks_per_day=settings.blocks_per_day,
            hours_per_block=settings.hours_per_block,
            end_date=target_date,
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
        for mi, ms in enumerate(spec.milestones):
            if target_date is not None:
                milestone_dates = dates_by_milestone[mi]
                due = milestone_dates[-1] if milestone_dates else target_date
            else:
                due = start + timedelta(days=ms.target_date_offset_days)
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
