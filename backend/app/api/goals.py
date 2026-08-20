import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Goal, Task, User
from ..services.capacity import InsufficientCapacityError
from ..services.planner_service import create_goal_with_plan, replan_goal, preview_goal

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_date: date | None = None
    duration_value: StrictInt | None = Field(default=None, gt=0)
    duration_unit: Literal["day", "week", "month"] | None = None
    daily_hours: float = 2.0
    rejected_assumptions: list[str] | None = None
    rest_days: list[int] | None = None  # weekday numbers 0=Mon, 6=Sun

    @field_validator("daily_hours", mode="before")
    @classmethod
    def validate_daily_hours(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("daily_hours 必须是数字")
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite() or decimal_value <= 0:
            raise ValueError("daily_hours 必须是有限的正数")
        try:
            normalized = float(decimal_value)
        except (OverflowError, ValueError):
            raise ValueError("daily_hours 必须是有限的正数") from None
        if not math.isfinite(normalized):
            raise ValueError("daily_hours 必须是有限的正数")
        numerator, denominator = decimal_value.as_integer_ratio()
        if (numerator * 2) % denominator != 0:
            raise ValueError("daily_hours 必须以 0.5 小时递增")
        return normalized

    @model_validator(mode="after")
    def validate_schedule_input(self):
        if (self.duration_value is None) != (self.duration_unit is None):
            raise ValueError("duration_value 与 duration_unit 必须同时提供")
        if self.target_date is not None and self.duration_value is not None:
            raise ValueError("target_date 与预计完成时长不能同时提供")
        if self.target_date is not None and self.target_date < date.today():
            raise ValueError("target_date 不能早于今天")
        return self


def serialize_task(t):
    return {
        "id": t.id, "title": t.title, "description": t.description, "type": t.type,
        "scheduled_date": t.scheduled_date.isoformat() if t.scheduled_date else None,
        "effort": t.effort, "actual_minutes": t.actual_minutes,
        "order": t.order, "status": t.status,
        "verified": t.verified,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


def serialize_milestone(m):
    return {
        "id": m.id, "title": m.title, "description": m.description, "order": m.order,
        "due_date": m.due_date.isoformat() if m.due_date else None, "status": m.status,
        "tasks": [serialize_task(t) for t in sorted(m.tasks, key=lambda x: x.order)],
    }


def serialize_plan(plan):
    return {
        "id": plan.id, "strategy": plan.strategy, "status": plan.status,
        "milestones": [serialize_milestone(m) for m in sorted(plan.milestones, key=lambda x: x.order)],
    }


def serialize_goal(goal, include_plan=False):
    data = {
        "id": goal.id, "title": goal.title, "description": goal.description,
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "created_at": goal.created_at.isoformat(),
        "feed_token": goal.feed_token,
        "leave_dates": sorted(goal.get_leave_dates()) if hasattr(goal, 'get_leave_dates') else [],
    }
    if include_plan and goal.plan:
        data["plan"] = serialize_plan(goal.plan)
    return data


@router.post("/preview")
def preview(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = preview_goal(payload.title, payload.description, payload.target_date, payload.daily_hours)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"预览生成失败：{exc}")

    # Calculate basic stats
    total_hours = sum(t.effort_hours for m in result.milestones for t in m.tasks)

    return {
        "strategy": result.strategy,
        "assumptions": result.assumptions,
        "milestones": [
            {"title": m.title, "description": m.description, "order": m.order,
             "tasks": [{"title": t.title, "description": t.description, "type": t.type, "effort_hours": t.effort_hours}
                       for t in m.tasks]}
            for m in result.milestones
        ],
        "total_hours": round(total_hours, 1),
    }


class ReplanRequest(BaseModel):
    daily_hours: float | None = None
    rest_days: list[int] | None = None


@router.post("/{goal_id}/replan")
def replan(
    goal_id: int,
    payload: ReplanRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        goal = replan_goal(
            db, goal_id, user.id,
            daily_hours=payload.daily_hours if payload else None,
            rest_days=set(payload.rest_days) if payload and payload.rest_days else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InsufficientCapacityError as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    return serialize_goal(goal, include_plan=True)


@router.get("/{goal_id}/replan/preview")
def replan_preview(
    goal_id: int,
    daily_hours: float = Query(None),
    rest_days: str = Query(None, description="逗号分隔的休息日，如 0,6 表示周一和周日"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """预览重排结果，不实际执行"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal or not goal.plan:
        raise HTTPException(status_code=404, detail="目标不存在")

    today = date.today()
    bpday = settings.blocks_per_day
    hpb = settings.hours_per_block
    dh = daily_hours or (bpday * hpb)
    _rest = set()
    if rest_days:
        try:
            _rest = {int(d.strip()) for d in rest_days.split(",") if d.strip()}
        except ValueError:
            pass

    # Collect incomplete tasks
    incomplete = []
    for milestone in sorted(goal.plan.milestones, key=lambda m: m.order):
        for task in sorted(milestone.tasks, key=lambda t: t.order):
            if task.status != "done":
                incomplete.append(task)

    if not incomplete:
        return {"changes": [], "total_days": 0, "daily_hours": dh}

    # Build virtual spec for scheduling
    virtual_tasks = [
        TaskSpec(title=t.title, description=t.description, type=t.type, effort_hours=t.effort)
        for t in incomplete
    ]
    virtual_spec = PlanSpec(strategy="replan", milestones=[
        MilestoneSpec(title="剩余任务", order=0, tasks=virtual_tasks)
    ])

    try:
        scheduled = schedule(
            virtual_spec, today,
            blocks_per_day=bpday, hours_per_block=hpb,
            end_date=goal.target_date, daily_hours=dh,
            rest_days=_rest,
        )
    except ValueError:
        scheduled = schedule(
            virtual_spec, today,
            blocks_per_day=bpday, hours_per_block=hpb,
            daily_hours=dh,
            rest_days=_rest,
        )

    changes = []
    for idx, task in enumerate(incomplete):
        new_date = scheduled[idx].date if idx < len(scheduled) else None
        changes.append({
            "task_id": task.id,
            "title": task.title,
            "old_date": task.scheduled_date.isoformat() if task.scheduled_date else None,
            "new_date": new_date.isoformat() if new_date else None,
        })

    total_days = (max(s.date for s in scheduled) - today).days + 1 if scheduled else 0
    return {"changes": changes, "total_days": total_days, "daily_hours": dh}


@router.get("/{goal_id}/pace")
def get_pace(
    goal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal or not goal.plan:
        raise HTTPException(status_code=404, detail="目标不存在")

    all_tasks = [t for m in goal.plan.milestones for t in m.tasks]
    if not all_tasks:
        return {"total_tasks": 0, "completed_tasks": 0, "planned_hours": 0, "actual_hours": 0,
                "deviation_pct": 0, "estimated_completion_date": None, "suggestion": None}

    completed_tasks = [t for t in all_tasks if t.status == "done"]
    planned_hours = sum(t.effort for t in all_tasks)
    actual_hours = sum((t.actual_minutes or t.effort * 60) / 60 for t in completed_tasks)
    planned_completed_hours = sum(t.effort for t in completed_tasks)
    deviation_pct = ((actual_hours - planned_completed_hours) / planned_completed_hours * 100) if planned_completed_hours > 0 else 0

    remaining_hours = sum(t.effort for t in all_tasks if t.status != "done")
    estimated_completion_date = None
    if completed_tasks and remaining_hours > 0:
        completions = [t.completed_at for t in completed_tasks if t.completed_at]
        if completions:
            days_elapsed = (datetime.now() - min(completions)).days or 1
            daily_rate = actual_hours / days_elapsed
            if daily_rate > 0:
                from datetime import timedelta as td
                estimated_completion_date = (date.today() + td(days=int(remaining_hours / daily_rate))).isoformat()

    suggestion = None
    if abs(deviation_pct) > 30:
        if goal.target_date and estimated_completion_date and estimated_completion_date > goal.target_date.isoformat():
            suggestion = {"type": "extend_deadline", "message": f"按当前速度，建议将期限延至 {estimated_completion_date}",
                          "suggested_deadline": estimated_completion_date}
        elif deviation_pct > 0:
            suggestion = {"type": "increase_budget", "message": f"实际比预计慢 {deviation_pct:.0f}%，建议增加每日预算"}
        else:
            suggestion = {"type": "decrease_budget", "message": f"实际比预计快 {abs(deviation_pct):.0f}%，可适当减少每日预算"}

    return {
        "total_tasks": len(all_tasks), "completed_tasks": len(completed_tasks),
        "planned_hours": round(planned_hours, 1), "actual_hours": round(actual_hours, 1),
        "planned_completed_hours": round(planned_completed_hours, 1), "deviation_pct": round(deviation_pct, 1),
        "remaining_hours": round(remaining_hours, 1), "estimated_completion_date": estimated_completion_date,
        "suggestion": suggestion,
    }


@router.post("", status_code=201)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        goal = create_goal_with_plan(
            db,
            payload.title,
            payload.description,
            target_date=payload.target_date,
            duration_value=payload.duration_value,
            duration_unit=payload.duration_unit,
            daily_hours=payload.daily_hours,
            user_id=user.id,
            rejected_assumptions=payload.rejected_assumptions,
            rest_days=set(payload.rest_days) if payload.rest_days else None,
        )
    except InsufficientCapacityError as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"计划生成失败：{exc}")
    return serialize_goal(goal, include_plan=True)


@router.get("")
def list_goals(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user.id)
        .order_by(Goal.created_at.desc())
        .all()
    )
    return [serialize_goal(g) for g in goals]


@router.get("/{goal_id}")
def get_goal(
    goal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")
    return serialize_goal(goal, include_plan=True)


class LeaveRequest(BaseModel):
    date: date


@router.post("/{goal_id}/leave")
def add_leave(
    goal_id: int,
    payload: LeaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """请假：标记某天为休息日，后续任务自动后延"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")

    goal.add_leave_date(payload.date)

    # Shift tasks scheduled on or after the leave date
    leave_date = payload.date
    for milestone in goal.plan.milestones if goal.plan else []:
        for task in milestone.tasks:
            if task.scheduled_date and task.scheduled_date >= leave_date:
                task.scheduled_date = task.scheduled_date + timedelta(days=1)

    # Update target_date
    all_dates = [t.scheduled_date for m in (goal.plan.milestones if goal.plan else []) for t in m.tasks if t.scheduled_date]
    if all_dates:
        goal.target_date = max(all_dates)

    db.commit()
    db.refresh(goal)
    return serialize_goal(goal, include_plan=True)


@router.delete("/{goal_id}/leave/{leave_date}")
def remove_leave(
    goal_id: int,
    leave_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """取消请假：日程恢复"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")

    goal.remove_leave_date(leave_date)

    # Shift tasks back: tasks on or after leave_date move back by 1 day
    for milestone in goal.plan.milestones if goal.plan else []:
        for task in milestone.tasks:
            if task.scheduled_date and task.scheduled_date > leave_date:
                task.scheduled_date = task.scheduled_date - timedelta(days=1)

    # Update target_date
    all_dates = [t.scheduled_date for m in (goal.plan.milestones if goal.plan else []) for t in m.tasks if t.scheduled_date]
    if all_dates:
        goal.target_date = max(all_dates)
    db.commit()
    db.refresh(goal)
    return serialize_goal(goal, include_plan=True)


@router.get("/{goal_id}/calendar.ics")
def export_calendar(
    goal_id: int,
    token: str = Query(None, description="Feed token for subscription"),
    db: Session = Depends(get_db),
):
    # Token-based auth for subscription (no login required)
    if token:
        goal = db.query(Goal).filter(Goal.id == goal_id, Goal.feed_token == token).first()
        if not goal:
            raise HTTPException(status_code=401, detail="无效的 feed token")
    else:
        # Without token, require user auth via cookie/session
        from ..auth import get_current_user
        from fastapi import Request
        raise HTTPException(status_code=401, detail="需要提供 feed token")

    if not goal.plan:
        raise HTTPException(status_code=404, detail="目标不存在")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Daybreak//Daybreak//ZH-CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{goal.title}",
    ]
    for milestone in sorted(goal.plan.milestones, key=lambda item: item.order):
        for task in sorted(milestone.tasks, key=lambda item: item.order):
            if task.scheduled_date is None:
                continue
            start = task.scheduled_date
            end = start + timedelta(days=1)
            status = "COMPLETED" if task.status == "done" else "TENTATIVE"
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:planagent-{task.id}@planagent",
                f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                f"SUMMARY:{task.title}",
                f"STATUS:{status}",
            ])
            if task.description:
                lines.append(f"DESCRIPTION:{task.description}")
            lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    content = "\r\n".join(lines) + "\r\n"
    return Response(
        content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="planagent-{goal.id}.ics"',
                 "Cache-Control": "no-cache, must-revalidate"},
    )


@router.get("/{goal_id}/review")
def get_review(
    goal_id: int,
    week: str = Query(None, description="ISO week YYYY-WW"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from collections import defaultdict

    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal or not goal.plan:
        raise HTTPException(status_code=404, detail="目标不存在")

    if week:
        try:
            yr, wk = map(int, week.split("-"))
            jan1 = date(yr, 1, 1)
            start_of_week = jan1 + timedelta(days=(wk - 1) * 7 - jan1.weekday())
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="周格式无效，请使用 YYYY-WW")
    else:
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        yr, wk = today.isocalendar()[0], today.isocalendar()[1]

    end_of_week = start_of_week + timedelta(days=6)
    all_tasks = [t for m in goal.plan.milestones for t in m.tasks]

    daily_stats = defaultdict(lambda: {"planned": 0, "completed": 0, "actual_minutes": 0})
    total_planned = total_completed = total_actual = verified_count = verification_count = 0

    for task in all_tasks:
        if task.scheduled_date and start_of_week <= task.scheduled_date <= end_of_week:
            day_key = task.scheduled_date.isoformat()
            daily_stats[day_key]["planned"] += 1
            total_planned += 1
            if task.status == "done":
                daily_stats[day_key]["completed"] += 1
                total_completed += 1
                if task.actual_minutes:
                    daily_stats[day_key]["actual_minutes"] += task.actual_minutes
                    total_actual += task.actual_minutes
            for record in task.verifications:
                verification_count += 1
                if record.passed:
                    verified_count += 1

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    daily = []
    cur = start_of_week
    while cur <= end_of_week:
        dk = cur.isoformat()
        s = daily_stats.get(dk, {"planned": 0, "completed": 0, "actual_minutes": 0})
        daily.append({"date": dk, "weekday": weekdays[cur.weekday()],
                      "planned_tasks": s["planned"], "completed_tasks": s["completed"],
                      "actual_minutes": s["actual_minutes"]})
        cur += timedelta(days=1)

    completion_rate = (total_completed / total_planned * 100) if total_planned > 0 else 0
    verification_rate = (verified_count / verification_count * 100) if verification_count > 0 else 0

    if completion_rate >= 90:
        conclusion = "本周表现优秀，继续保持！"
    elif completion_rate >= 70:
        conclusion = "本周完成率良好，可以适当提高目标。"
    elif completion_rate >= 50:
        conclusion = "本周完成率一般，建议调整计划或增加时间投入。"
    else:
        conclusion = "本周完成率较低，建议重新评估目标可行性。"

    return {
        "year": yr, "week": wk,
        "start_date": start_of_week.isoformat(), "end_date": end_of_week.isoformat(),
        "total_planned": total_planned, "total_completed": total_completed,
        "completion_rate": round(completion_rate, 1),
        "total_actual_minutes": total_actual,
        "verification_count": verification_count, "verified_count": verified_count,
        "verification_rate": round(verification_rate, 1),
        "daily": daily, "conclusion": conclusion,
    }


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")
    db.delete(goal)
    db.commit()
    return {"ok": True}
