# Task 5: 计划生成服务(LLM + 排程 + 落库)

## 目标

实现 `create_goal_with_plan()`,串联:建 Goal → LLM 生成 PlanSpec → 排程得日期 → 落库 Plan/Milestone/Task。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 5** 一节。

## 要创建的文件

- `backend/app/services/__init__.py`(空包)
- `backend/app/services/planner_service.py`
- `backend/tests/test_planner_service.py`

## 关键接口(后续任务依赖,必须一致)

```python
def create_goal_with_plan(db: Session, title: str, description: str = "",
                          target_date: date | None = None) -> Goal
```

## 实现内容

### `backend/app/services/planner_service.py`

```python
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
    db.commit()
    db.refresh(goal)

    spec = generate_plan(title, description, target_date.isoformat() if target_date else None)
    start = date.today()
    scheduled = schedule(
        spec, start, blocks_per_day=settings.blocks_per_day, hours_per_block=settings.hours_per_block
    )
    by_key = {(r.milestone_order, r.task_index): r.date for r in scheduled}

    plan = Plan(goal_id=goal.id, strategy=spec.strategy, status="active")
    db.add(plan)
    db.flush()
    for ms in spec.milestones:
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
                type=t.type, scheduled_date=by_key[(ms.order, idx)],
                effort=t.effort_hours, order=idx, status="todo", verified=False,
            ))
    db.commit()
    db.refresh(goal)
    return goal
```

### `backend/tests/test_planner_service.py`

```python
from datetime import date, timedelta

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.models import Goal
from app.services.planner_service import create_goal_with_plan


def _fake_spec():
    return PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="里程碑1", order=1, target_date_offset_days=7,
            tasks=[
                TaskSpec(title="任务1", type="learn", effort_hours=1.0),
                TaskSpec(title="任务2", type="practice", effort_hours=2.0),
            ],
        )],
    )


def test_create_goal_persists_full_tree(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _fake_spec()
    )
    goal = create_goal_with_plan(db_session, "目标", "说明", date(2026, 11, 13))
    db_session.refresh(goal)
    assert goal.plan is not None
    ms = goal.plan.milestones[0]
    assert ms.title == "里程碑1"
    assert ms.due_date == date.today() + timedelta(days=7)  # start=today + 7 offset
    assert len(ms.tasks) == 2
    # 任务1(1h)+任务2(2h),每天2块 → 任务2 顺延到次日
    assert ms.tasks[0].scheduled_date == date.today()
    assert ms.tasks[1].scheduled_date == date.today() + timedelta(days=1)
    assert ms.tasks[1].verified is False
```

注意:测试用相对日期断言,不要改成硬编码日期。

## 完成标准

1. 先写测试确认失败 → 再实现 → `cd backend && python -m pytest tests/test_planner_service.py -v` → `1 passed`
2. 创建 git commit(`feat: goal creation service wiring llm+scheduler+storage`)
3. 报告:提交 hash、测试摘要、concerns

## 提交命令

```bash
git add backend/app/services backend/tests/test_planner_service.py
git commit -m "feat: goal creation service wiring llm+scheduler+storage"
```

## 报告

<!-- Codex: 完成后在此填写 -->
