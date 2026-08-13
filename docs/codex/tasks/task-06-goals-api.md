# Task 6: Goals API

## 目标

实现 Goals REST 路由:POST / GET / GET /{id} / DELETE,含序列化函数;注册进 main.py;写 API 测试。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 6** 一节。

## 要创建/修改的文件

- Create `backend/app/api/__init__.py`(空包)
- Create `backend/app/api/goals.py`
- Modify `backend/app/main.py`(注册 router)
- Create `backend/tests/test_goals_api.py`

## 路由(前端依赖,字段名必须一致)

```
POST   /api/goals    body {title, description?, target_date?} → 201, serialize_goal(goal, include_plan=True)
GET    /api/goals                    → list[serialize_goal]
GET    /api/goals/{id}               → 404 或 serialize_goal(include_plan=True)
DELETE /api/goals/{id}               → {"ok": true} 或 404
```

序列化字段:task `id,title,description,type,scheduled_date,effort,order,status,verified,completed_at`;milestone `id,title,description,order,due_date,status,tasks[](按 order 排序)`;plan `id,strategy,status,milestones[](按 order 排序)`;goal `id,title,description,target_date,created_at`(include_plan 时加 plan)。

POST 里 LLM 失败(任何异常)返回 `HTTPException(502, f"计划生成失败：{exc}")`。

## 实现内容

### `backend/app/api/goals.py`

```python
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
```

### `backend/app/main.py`(修改)

在 `app.include_router(goals.router)` 前加导入 `from .api import goals`,并在创建 `app` 后加 `app.include_router(goals.router)`。

### `backend/tests/test_goals_api.py`

```python
from app.models import Goal, Milestone, Plan, Task


def _build_goal(db_session):
    goal = Goal(title="目标", description="说明")
    db_session.add(goal)
    plan = Plan(goal_id=0, strategy="策略")
    goal.plan = plan
    ms = Milestone(title="里程碑1", order=1)
    plan.milestones.append(ms)
    ms.tasks.append(Task(title="任务1", type="learn", order=0, effort=1.0))
    db_session.commit()
    return goal


def test_create_goal(client, db_session, monkeypatch):
    from app.services.planner_service import create_goal_with_plan

    def fake(title, description, target_date):
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    res = client.post("/api/goals", json={"title": "目标", "description": "说明"})
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "目标"
    assert body["plan"]["milestones"][0]["tasks"][0]["title"] == "任务1"


def test_get_goal_not_found(client):
    res = client.get("/api/goals/999")
    assert res.status_code == 404


def test_delete_goal(client, db_session, monkeypatch):
    from app.services.planner_service import create_goal_with_plan

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", lambda *a, **k: _build_goal(db_session))
    created = client.post("/api/goals", json={"title": "目标"}).json()
    res = client.delete(f"/api/goals/{created['id']}")
    assert res.status_code == 200
    assert client.get(f"/api/goals/{created['id']}").status_code == 404


def test_list_goals(client, db_session, monkeypatch):
    from app.services.planner_service import create_goal_with_plan

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", lambda *a, **k: _build_goal(db_session))
    client.post("/api/goals", json={"title": "目标A"})
    client.post("/api/goals", json={"title": "目标B"})
    res = client.get("/api/goals")
    assert res.status_code == 200
    assert len(res.json()) == 2
```

## 完成标准

1. `cd backend && python -m pytest tests/test_goals_api.py -v` → `4 passed`
2. 创建 git commit(`feat: goals REST api`)
3. 报告:提交 hash、测试摘要、concerns

## 提交命令

```bash
git add backend/app/api backend/app/main.py backend/tests/test_goals_api.py
git commit -m "feat: goals REST api"
```

## 报告

- 提交 hash: `707cf99`
- pytest 摘要: `python -m pytest tests/test_goals_api.py -v` → `4 passed, 1 warning in 0.13s`
- concerns:
  - 当前受限沙箱禁止 pytest 写 SQLite/缓存，RED/GREEN 验证均在获批的沙箱外执行。
  - 任务卡首个 fake 的签名遗漏 `db` 参数，已按权威服务接口修正为 `(db, title, description, target_date)`。
  - `sqlite:///:memory:` 默认连接在线程间不共享，FastAPI 同步路由看不到 fixture 建表；已在测试 engine 加 `StaticPool`。
  - 原模型缺少 Goal→Plan 删除级联，DELETE 会尝试将非空 `plans.goal_id` 置空；已为一对一所有权关系补 `cascade="all, delete-orphan"`。
  - 存在 1 条第三方 `StarletteDeprecationWarning`。
