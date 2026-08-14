import math
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Goal
from ..services.capacity import InsufficientCapacityError
from ..services.planner_service import create_goal_with_plan

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_date: date | None = None
    duration_value: StrictInt | None = Field(default=None, gt=0)
    duration_unit: Literal["day", "week", "month"] | None = None
    daily_hours: float = 2.0

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
        "effort": t.effort, "order": t.order, "status": t.status,
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
    }
    if include_plan and goal.plan:
        data["plan"] = serialize_plan(goal.plan)
    return data


@router.post("", status_code=201)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)):
    try:
        goal = create_goal_with_plan(
            db,
            payload.title,
            payload.description,
            target_date=payload.target_date,
            duration_value=payload.duration_value,
            duration_unit=payload.duration_unit,
            daily_hours=payload.daily_hours,
        )
    except InsufficientCapacityError as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"计划生成失败：{exc}")
    return serialize_goal(goal, include_plan=True)


@router.get("")
def list_goals(db: Session = Depends(get_db)):
    goals = db.query(Goal).order_by(Goal.created_at.desc()).all()
    return [serialize_goal(g) for g in goals]


@router.get("/{goal_id}")
def get_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")
    return serialize_goal(goal, include_plan=True)


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="目标不存在")
    db.delete(goal)
    db.commit()
    return {"ok": True}
