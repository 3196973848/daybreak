from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Goal
from ..services.planner_service import create_goal_with_plan

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_date: date | None = None


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
        goal = create_goal_with_plan(db, payload.title, payload.description, payload.target_date)
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
