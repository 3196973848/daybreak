from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..llm.planner import generate_plan
from ..models import Goal, Milestone, Plan, Task
from ..scheduler.scheduler import schedule


def create_goal_with_plan(
    db: Session,
    title: str,
    description: str = "",
    target_date: date | None = None,
) -> Goal:
    goal = Goal(title=title, description=description, target_date=target_date)
    db.add(goal)
    db.flush()

    try:
        spec = generate_plan(title, description, target_date.isoformat() if target_date else None)
        start = date.today()
        scheduled = schedule(
            spec, start, blocks_per_day=settings.blocks_per_day, hours_per_block=settings.hours_per_block
        )
        by_key = {(r.milestone_index, r.task_index): r.date for r in scheduled}

        plan = Plan(goal_id=goal.id, strategy=spec.strategy, status="active")
        db.add(plan)
        db.flush()
        for mi, ms in enumerate(spec.milestones):
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
