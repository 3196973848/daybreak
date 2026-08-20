import math
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..llm.planner import generate_plan, generate_preview
from ..llm.schema import MilestoneSpec, PlanSpec, PreviewSpec, TaskSpec
from ..models import Goal, Milestone, Plan, Task
from ..scheduler.duration import DurationUnit, calculate_target_date
from ..scheduler.scheduler import group_tasks, schedule
from .capacity import InsufficientCapacityError
from .plan_validation import PlanValidationError, validate_atomic_plan


INVALID_MODEL_OUTPUT_FEEDBACK = (
    "上次模型输出为空、不是合法 JSON 或不符合计划结构；"
    "请只返回符合约定结构的完整 JSON 计划"
)


def create_goal_with_plan(
    db: Session,
    title: str,
    description: str = "",
    target_date: date | None = None,
    duration_value: int | None = None,
    duration_unit: DurationUnit | None = None,
    daily_hours: float = 2.0,
    user_id: int | None = None,
    rejected_assumptions: list[str] | None = None,
    rest_days: set[int] | None = None,
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
            try:
                spec = generate_plan(
                    title,
                    description,
                    target_date.isoformat() if target_date else None,
                    daily_hours=daily_hours,
                    feedback=feedback,
                    rejected_assumptions=rejected_assumptions,
                )
                validate_atomic_plan(spec, daily_hours)
                break
            except PlanValidationError as exc:
                feedback = f"{exc}；请确保单个任务不超过每日投入时间"
                if attempt == 2:
                    raise RuntimeError("无法生成有效的原子计划") from None
            except RuntimeError:
                feedback = INVALID_MODEL_OUTPUT_FEEDBACK
                if attempt == 2:
                    raise RuntimeError("无法生成有效的原子计划") from None

        groups = group_tasks(spec, daily_hours)
        _rest = rest_days or set()
        if target_date is not None:
            required_hours = sum(
                task.effort_hours
                for milestone in spec.milestones
                for task in milestone.tasks
            )
            # Count working days (excluding rest days)
            working_day_count = 0
            d = start
            while d <= target_date:
                if d.weekday() not in _rest:
                    working_day_count += 1
                d += timedelta(days=1)
            minimum_days = max(
                math.ceil(required_hours / daily_hours),
                len(groups),
            )
            # Auto-extend target_date if capacity is insufficient
            if minimum_days > working_day_count:
                extra_days = minimum_days - working_day_count
                target_date = target_date + timedelta(days=extra_days * 2)  # generous buffer

        goal = Goal(
            title=title,
            description=description,
            target_date=target_date,
            user_id=user_id,
        )
        db.add(goal)
        db.flush()
        scheduled = schedule(
            spec,
            start,
            blocks_per_day=settings.blocks_per_day,
            hours_per_block=settings.hours_per_block,
            end_date=target_date,
            daily_hours=daily_hours,
            rest_days=rest_days,
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
        # Update target_date to actual last scheduled task date
        all_dates = [r.date for r in scheduled]
        if all_dates:
            goal.target_date = max(all_dates)
        db.flush()
        db.refresh(goal)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return goal


def replan_goal(db: Session, goal_id: int, user_id: int, daily_hours: float | None = None, rest_days: set[int] | None = None) -> Goal:
    """增量重排：已完成任务不动，未完成任务从今天起重新调度"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if not goal:
        raise ValueError("目标不存在")
    if not goal.plan:
        raise ValueError("目标没有计划")

    today = date.today()
    incomplete_tasks: list[tuple[int, Task]] = []
    for milestone in sorted(goal.plan.milestones, key=lambda m: m.order):
        for task in sorted(milestone.tasks, key=lambda t: t.order):
            if task.status != "done":
                incomplete_tasks.append((len(incomplete_tasks), task))

    if not incomplete_tasks:
        return goal

    # Build a virtual PlanSpec for scheduling
    virtual_tasks = [
        TaskSpec(title=t.title, description=t.description, type=t.type, effort_hours=t.effort)
        for _, t in incomplete_tasks
    ]
    virtual_spec = PlanSpec(strategy="replan", milestones=[
        MilestoneSpec(title="剩余任务", order=0, tasks=virtual_tasks)
    ])

    dh = daily_hours or (settings.blocks_per_day * settings.hours_per_block)
    # Combine weekly rest days with leave dates
    _rest = rest_days or set()
    _leave = goal.get_leave_dates()

    if goal.target_date:
        from .capacity import InsufficientCapacityError
        required_hours = sum(t.effort for _, t in incomplete_tasks)
        # Count working days
        _rest = rest_days or set()
        working_days = 0
        d = today
        while d <= goal.target_date:
            if d.weekday() not in _rest:
                working_days += 1
            d += timedelta(days=1)
        groups = group_tasks(virtual_spec, dh)
        minimum_days = max(math.ceil(required_hours / dh), len(groups))
        if minimum_days > working_days:
            raise InsufficientCapacityError(required_hours, working_days * dh, minimum_days)

    scheduled = schedule(
        virtual_spec, today,
        blocks_per_day=settings.blocks_per_day,
        hours_per_block=settings.hours_per_block,
        end_date=goal.target_date,
        daily_hours=dh,
        rest_days=_rest,
        skip_dates=_leave,
    )

    for idx, (_, task) in enumerate(incomplete_tasks):
        if idx < len(scheduled):
            task.scheduled_date = scheduled[idx].date

    # Update target_date to new last scheduled task date
    all_dates = [s.date for s in scheduled]
    if all_dates:
        goal.target_date = max(all_dates)

    db.commit()
    db.refresh(goal)
    return goal


def preview_goal(
    title: str, description: str = "", target_date: date | None = None, daily_hours: float = 2.0
) -> PreviewSpec:
    """生成预览：只返回里程碑大纲和假设清单，不写库"""
    return generate_preview(title, description, target_date.isoformat() if target_date else None, daily_hours=daily_hours)
