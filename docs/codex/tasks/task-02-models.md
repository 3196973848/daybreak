# Task 2: SQLAlchemy 数据模型

## 目标

定义 Goal / Plan / Milestone / Task / VerificationRecord 五个 ORM 模型,字段与 spec §4 一致,并写往返测试。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 2** 一节。

## 要创建的文件

- `backend/app/models.py`
- `backend/tests/test_models.py`

## 实现内容

### `backend/app/models.py`

```python
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    plan: Mapped["Plan"] = relationship(back_populates="goal", uselist=False)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"))
    strategy: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    goal: Mapped[Goal] = relationship(back_populates="plan")
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    plan: Mapped[Plan] = relationship(back_populates="milestones")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="milestone", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestones.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(20), default="learn")
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effort: Mapped[float] = mapped_column(Float, default=1.0)
    order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    milestone: Mapped[Milestone] = relationship(back_populates="tasks")
    verifications: Mapped[list["VerificationRecord"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    mode: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    submission: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    task: Mapped[Task] = relationship(back_populates="verifications")
```

### `backend/tests/test_models.py`

```python
from app.models import Goal, Milestone, Plan, Task, VerificationRecord


def test_goal_tree_roundtrip(db_session):
    goal = Goal(title="目标", description="说明")
    db_session.add(goal)
    plan = Plan(goal_id=0, strategy="策略")
    goal.plan = plan
    ms = Milestone(title="里程碑1", order=1)
    plan.milestones.append(ms)
    t = Task(title="任务1", type="learn", order=0, effort=1.0)
    ms.tasks.append(t)
    t.verifications.append(VerificationRecord(mode="test", content="{}"))
    db_session.commit()

    got = db_session.get(Goal, goal.id)
    assert got.plan.strategy == "策略"
    assert got.plan.milestones[0].tasks[0].title == "任务1"
    assert got.plan.milestones[0].tasks[0].verifications[0].mode == "test"
```

注:`Plan(goal_id=0)` 仅占位,关系赋值 `goal.plan = plan` 会修正外键。

## 完成标准

1. `cd backend && python -m pytest tests/test_models.py -v` → `1 passed`
2. 创建 git commit(`feat: sqlalchemy models for goal/plan/milestone/task/verification`)
3. 报告:提交 hash、测试摘要、concerns

## 依赖

Task 1 已提供 `app.database.Base`。

## 提交命令

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: sqlalchemy models for goal/plan/milestone/task/verification"
```

## 报告

- 提交 hash: `cd5f40e`
- pytest 摘要: `python -m pytest tests/test_models.py -v` → `1 passed, 1 warning in 0.05s`
- concerns:
  - 当前受限沙箱禁止 pytest 写 SQLite/缓存，验收命令在获批的沙箱外执行。
  - 与 Task 01 相同，存在 1 条第三方 `StarletteDeprecationWarning`，不影响模型往返测试。
