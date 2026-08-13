# PlanAgent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个目标驱动的规划 Web 应用 —— 用户输入目标,LLM 拆解成里程碑和每日任务,排程算法排出日程,前端展示并支持勾选完成与检验。

**Architecture:** FastAPI 后端(LLM 编排 + 确定性排程 + SQLite 存储 + REST API)与 React/Vite 前端(SPA)分离,通过 `/api` 代理通信。LLM 只产出"是什么"(策略+里程碑+任务+工时),排程算法负责"哪天做"。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / SQLite / Anthropic SDK (`claude-opus-4-8`) / React 18 / Vite / TypeScript / react-router。

**Spec:** `docs/superpowers/specs/2026-08-13-planagent-design.md`(本计划依据该 spec,执行者需同时阅读两者)

## Global Constraints

- 数据模型按 spec §4:Goal → 1 Plan → N Milestone → N Task,另加 VerificationRecord
- LLM 调用统一走 Anthropic Python SDK 的 `client.messages.parse(..., output_format=Model)`,模型 ID 用 `claude-opus-4-8`,`thinking={"type": "adaptive"}`
- LLM 只输出"是什么",绝不输出具体日期;日期一律由 `schedule()` 算法产生
- 检验通过阈值:测试/交付的 `score >= 0.7` 判通过(在服务端计算,不依赖 LLM 返回 passed)
- 前端配色为黑灰主题:背景 `#000000`、卡片 `#1a1a1a`、边框 `#2e2e2e`、强调/主文字 `#e5e5e5`、次要 `#a3a3a3`、弱化 `#737373`
- 前端界面文案用中文
- API key 走环境变量 `ANTHROPIC_API_KEY`(SDK 自动读取),不硬编码
- 所有后端路由前缀为 `/api`

---

### Task 1: 后端脚手架 + 健康检查

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.settings`(pydantic-settings 单例,含 `database_url`/`blocks_per_day`/`hours_per_block`/`anthropic_model`)
- Produces: `app.database.Base`(DeclarativeBase)、`engine`、`SessionLocal`、`init_db()`、`get_db()`(FastAPI 依赖)
- Produces: `app.main.app`(FastAPI 实例,`GET /api/health` 返回 `{"status": "ok"}`)

- [ ] **Step 1: 写依赖文件**

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.34
sqlalchemy>=2.0
pydantic>=2.7
pydantic-settings>=2.3
anthropic>=0.116
httpx>=0.27
pytest>=8
```

- [ ] **Step 2: 写 config 与 database 模块**

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./planagent.db"
    blocks_per_day: int = 2
    hours_per_block: float = 1.0
    anthropic_model: str = "claude-opus-4-8"

    model_config = {"env_prefix": "PLANAGENT_"}


settings = Settings()
```

`backend/app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  ensure models are registered on Base

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: 写 main 应用**

`backend/app/main.py`:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PlanAgent", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: 写测试基建(conftest)**

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 5: 写健康检查测试**

`backend/tests/test_health.py`:
```python
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: `1 passed`。(若 `app` 不在路径,先 `pip install -r requirements.txt`,并在 `backend` 下建 `pytest.ini`:
```
[pytest]
pythonpath = .
```

- [ ] **Step 7: 提交**

```bash
git add backend/requirements.txt backend/app backend/tests
git commit -m "feat: backend scaffold with health check"
```

---

### Task 2: SQLAlchemy 数据模型

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.database.Base`
- Produces: ORM 类 `Goal` / `Plan` / `Milestone` / `Task` / `VerificationRecord`,字段名与 spec §4 一致。Task 有 `type`、`verified`、`status`、`scheduled_date`、`effort`、`order`、`completed_at`。

- [ ] **Step 1: 写模型**

`backend/app/models.py`:
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

- [ ] **Step 2: 写往返测试**

`backend/tests/test_models.py`:
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

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: `1 passed`。(`Plan(goal_id=0)` 仅占位,关系赋值 `goal.plan = plan` 会修正外键。)

- [ ] **Step 4: 提交**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: sqlalchemy models for goal/plan/milestone/task/verification"
```

---

### Task 3: 排程算法(纯函数)

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/schema.py`
- Create: `backend/app/scheduler/__init__.py`
- Create: `backend/app/scheduler/scheduler.py`
- Create: `backend/tests/test_scheduler.py`

**Interfaces:**
- Produces: `app.llm.schema.TaskSpec(title, description, type, effort_hours)`、`MilestoneSpec(title, description, order, target_date_offset_days, tasks)`、`PlanSpec(strategy, milestones)`(Pydantic 模型)
- Produces: `app.scheduler.scheduler.schedule(plan_spec, start_date, blocks_per_day=2, hours_per_block=1.0) -> list[ScheduledTask]`,其中 `ScheduledTask(milestone_order, task_index, date)`
- 排程规则:任务按 order 串行;每天容量 = `blocks_per_day` 块,每块 `hours_per_block` 小时;任务需 `ceil(effort_hours / hours_per_block)` 块,当日放不下则顺延到次日。

- [ ] **Step 1: 写 LLM 输出 schema(供排程与 LLM 共用)**

`backend/app/llm/schema.py`:
```python
from typing import List

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    title: str
    description: str = ""
    type: str = "learn"
    effort_hours: float = Field(default=1.0)


class MilestoneSpec(BaseModel):
    title: str
    description: str = ""
    order: int = 0
    target_date_offset_days: int = Field(default=7, ge=1)
    tasks: List[TaskSpec]


class PlanSpec(BaseModel):
    strategy: str = ""
    milestones: List[MilestoneSpec]
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_scheduler.py`:
```python
from datetime import date

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.scheduler.scheduler import schedule


def _plan(*tasks):
    return PlanSpec(
        strategy="s",
        milestones=[MilestoneSpec(title="M", order=1, target_date_offset_days=7, tasks=list(tasks))],
    )


def test_tasks_fit_in_one_day():
    plan = _plan(
        TaskSpec(title="a", type="learn", effort_hours=1.0),
        TaskSpec(title="b", type="learn", effort_hours=1.0),
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [r.date for r in result] == [date(2026, 8, 13), date(2026, 8, 13)]


def test_task_overflows_to_next_day():
    plan = _plan(
        TaskSpec(title="a", type="learn", effort_hours=1.0),
        TaskSpec(title="b", type="project", effort_hours=3.0),
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [r.date for r in result] == [date(2026, 8, 13), date(2026, 8, 14)]


def test_respects_milestone_order_and_index():
    plan = PlanSpec(
        strategy="s",
        milestones=[
            MilestoneSpec(title="M1", order=1, target_date_offset_days=3,
                          tasks=[TaskSpec(title="m1t", type="learn", effort_hours=1.0)]),
            MilestoneSpec(title="M2", order=2, target_date_offset_days=7,
                          tasks=[TaskSpec(title="m2t", type="learn", effort_hours=1.0)]),
        ],
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [(r.milestone_order, r.task_index, r.date) for r in result] == [
        (1, 0, date(2026, 8, 13)),
        (2, 0, date(2026, 8, 13)),
    ]
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.scheduler'`

- [ ] **Step 4: 实现排程**

`backend/app/scheduler/scheduler.py`:
```python
import math
from dataclasses import dataclass
from datetime import date, timedelta

from ..llm.schema import PlanSpec


@dataclass
class ScheduledTask:
    milestone_order: int
    task_index: int
    date: date


def schedule(
    plan: PlanSpec,
    start_date: date,
    blocks_per_day: int = 2,
    hours_per_block: float = 1.0,
) -> list[ScheduledTask]:
    """按里程碑顺序串行把任务铺到具体日期。当日剩余块不够则顺延次日。"""
    out: list[ScheduledTask] = []
    day = start_date
    blocks_left = blocks_per_day
    for ms in plan.milestones:
        for idx, task in enumerate(ms.tasks):
            needed = max(1, math.ceil(task.effort_hours / hours_per_block))
            if needed > blocks_left:
                day += timedelta(days=1)
                blocks_left = blocks_per_day
            out.append(ScheduledTask(ms.order, idx, day))
            blocks_left -= needed
    return out
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: `3 passed`

- [ ] **Step 6: 提交**

```bash
git add backend/app/llm backend/app/scheduler backend/tests/test_scheduler.py
git commit -m "feat: deterministic scheduler pure function"
```

---

### Task 4: LLM 计划生成模块

**Files:**
- Create: `backend/app/llm/planner.py`
- Create: `backend/tests/test_planner.py`

**Interfaces:**
- Consumes: `app.llm.schema.PlanSpec`、`app.config.settings.anthropic_model`
- Produces: `app.llm.planner.generate_plan(goal_title, description, target_date, client=None) -> PlanSpec`;`client` 参数默认为 `anthropic.Anthropic()`,便于测试注入 fake。

- [ ] **Step 1: 写失败测试(用 fake client)**

`backend/tests/test_planner.py`:
```python
from app.llm.planner import generate_plan
from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec


class FakeResponse:
    def __init__(self, parsed):
        self.parsed_output = parsed


class FakeMessages:
    def __init__(self, spec):
        self._spec = spec

    def parse(self, **kwargs):
        return FakeResponse(self._spec)


class FakeClient:
    def __init__(self, spec):
        self.messages = FakeMessages(spec)


def test_generate_plan_returns_spec():
    spec = PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="里程碑1", order=1, target_date_offset_days=7,
            tasks=[TaskSpec(title="任务1", type="learn", effort_hours=1.0)],
        )],
    )
    client = FakeClient(spec)
    got = generate_plan("目标", "说明", "2026-11-13", client=client)
    assert got == spec
    assert got.milestones[0].tasks[0].type == "learn"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_planner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm.planner'`

- [ ] **Step 3: 实现 planner**

`backend/app/llm/planner.py`:
```python
import anthropic

from ..config import settings
from .schema import PlanSpec

PLANNER_SYSTEM_PROMPT = """你是一个目标规划专家。用户给出一个目标，你要把它拆解成一份完整计划。

输出结构：
- strategy：一句话总体策略
- milestones：3-6 个阶段性小目标，按 order 排序；target_date_offset_days 为该里程碑相对计划开始日的天数偏移
- 每个 milestone 有 3-10 个 tasks，按学习顺序串行（先基础后进阶）

任务规则：
- 每个 task 有 type，取值 learn(学习)/practice(实操)/project(项目)
- effort_hours 为预估工时：学习 0.5-2，实操 1-4，项目 2-8
- 描述用中文，具体可执行"""


def generate_plan(
    goal_title: str,
    description: str,
    target_date: str | None,
    client: anthropic.Anthropic | None = None,
) -> PlanSpec:
    client = client or anthropic.Anthropic()
    user_prompt = f"目标：{goal_title}\n说明：{description or '无'}"
    if target_date:
        user_prompt += f"\n期望完成日期：{target_date}"
    user_prompt += "\n请生成完整计划。"
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=PLANNER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=PlanSpec,
    )
    if response.parsed_output is None:
        raise RuntimeError("LLM 输出解析失败")
    return response.parsed_output
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_planner.py -v`
Expected: `1 passed`

- [ ] **Step 5: 提交**

```bash
git add backend/app/llm/planner.py backend/tests/test_planner.py
git commit -m "feat: llm plan generation with structured output"
```

---

### Task 5: 计划生成服务(LLM + 排程 + 落库)

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/planner_service.py`
- Create: `backend/tests/test_planner_service.py`

**Interfaces:**
- Consumes: `generate_plan`、`schedule`、ORM 模型、`settings`
- Produces: `app.services.planner_service.create_goal_with_plan(db, title, description="", target_date=None) -> Goal`,落库后返回带完整 plan/milestones/tasks 的 Goal。若 LLM 抛错,向上传播由 API 层处理。

- [ ] **Step 1: 写失败测试(monkeypatch generate_plan)**

`backend/tests/test_planner_service.py`:
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

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_planner_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现服务**

`backend/app/services/planner_service.py`:
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

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_planner_service.py -v`
Expected: `1 passed`(若测试里 `date.today()` 跨天边界导致 flaky,改用冻结日期:在测试内 `monkeypatch` 前用固定 `start` 不易做,可接受极小概率失败;若担心,把断言改为相对偏移即可——见下条备注。)

- [ ] **Step 5: 提交**

```bash
git add backend/app/services backend/tests/test_planner_service.py
git commit -m "feat: goal creation service wiring llm+scheduler+storage"
```

---

### Task 6: Goals API

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/goals.py`
- Modify: `backend/app/main.py`(注册 router)
- Create: `backend/tests/test_goals_api.py`

**Interfaces:**
- Consumes: `create_goal_with_plan`、`get_db`
- Produces: 路由 `POST /api/goals`、`GET /api/goals`、`GET /api/goals/{id}`、`DELETE /api/goals/{id}`
- Produces: 序列化函数 `serialize_goal(goal, include_plan=False) -> dict`、`serialize_plan(plan) -> dict`(里程碑按 order、任务按 order 排序)

- [ ] **Step 1: 写路由模块**

`backend/app/api/goals.py`:
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
    except Exception as exc:  # LLM 失败 → 可重试错误
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

- [ ] **Step 2: 注册路由到 main**

`backend/app/main.py`(修改为):
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import goals
from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PlanAgent", lifespan=lifespan)
app.include_router(goals.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 3: 写 API 测试(monkeypatch 服务层)**

`backend/tests/test_goals_api.py`:
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

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_goals_api.py -v`
Expected: `4 passed`

- [ ] **Step 5: 提交**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_goals_api.py
git commit -m "feat: goals REST api"
```

---

### Task 7: LLM 检验模块(测试 / 交付)

**Files:**
- Create: `backend/app/llm/verifier.py`
- Create: `backend/tests/test_verifier.py`

**Interfaces:**
- Consumes: `settings.anthropic_model`
- Produces:
  - `generate_test(task_title, task_description, client=None) -> TestContent`(`TestContent.questions: list[Question]`,`Question(id, type='choice'|'short', text, options)`)
  - `grade_test(task_title, task_description, content: TestContent, answers: dict, client=None) -> GradeResult`
  - `generate_deliver_criteria(task_title, task_description, client=None) -> DeliverContent`(`DeliverContent.acceptance_criteria: str`)
  - `grade_delivery(task_title, task_description, criteria: str, submission: str, client=None) -> GradeResult`
  - `GradeResult(score: float, feedback: str)`;`passed` 由调用方按 `score >= 0.7` 计算

- [ ] **Step 1: 写失败测试**

`backend/tests/test_verifier.py`:
```python
from app.llm.verifier import (
    DeliverContent,
    GradeResult,
    TestContent,
    generate_deliver_criteria,
    generate_test,
    grade_delivery,
    grade_test,
)
from app.llm.schema import PlanSpec  # noqa: F401  (ensure schema import works)


class FakeResponse:
    def __init__(self, parsed):
        self.parsed_output = parsed


class FakeMessages:
    def __init__(self, value):
        self._value = value

    def parse(self, **kwargs):
        return FakeResponse(self._value)


class FakeClient:
    def __init__(self, value):
        self.messages = FakeMessages(value)


def test_generate_test():
    content = TestContent(questions=[
        {"id": 1, "type": "choice", "text": "哪个是变量名?", "options": ["a", "b"]},
        {"id": 2, "type": "short", "text": "什么是赋值?", "options": []},
    ])
    got = generate_test("任务", "内容", client=FakeClient(content))
    assert got.questions[0].type == "choice"


def test_grade_test_passed_threshold():
    grade = GradeResult(score=0.9, feedback="很好")
    got = grade_test("任务", "内容", TestContent(questions=[]), {"1": "a"}, client=FakeClient(grade))
    assert got.score >= 0.7


def test_generate_deliver_criteria():
    got = generate_deliver_criteria("写计算器", "支持四则运算", client=FakeClient(DeliverContent(acceptance_criteria="支持加减乘除")))
    assert got.acceptance_criteria == "支持加减乘除"


def test_grade_delivery():
    grade = GradeResult(score=0.5, feedback="不达标")
    got = grade_delivery("写计算器", "内容", "标准", "我的成果", client=FakeClient(grade))
    assert got.score < 0.7
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_verifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 verifier**

`backend/app/llm/verifier.py`:
```python
import json
from typing import List

import anthropic
from pydantic import BaseModel

from ..config import settings


class Question(BaseModel):
    id: int
    type: str  # choice | short
    text: str
    options: List[str] = []


class TestContent(BaseModel):
    questions: List[Question]


class DeliverContent(BaseModel):
    acceptance_criteria: str


class GradeResult(BaseModel):
    score: float
    feedback: str


TEST_GENERATE_PROMPT = """你是学习测试出题助手。基于学习任务内容生成 2-3 道选择题和 1 道简答题。
选择题必须含 4 个选项且仅一个正确；简答题 options 为空。只输出 JSON，不输出其它内容。"""

GRADE_TEST_PROMPT = """你是严格但公平的评分老师。依据学习任务内容与题目，判断用户答案正确率。
返回 JSON：{"score": 0-1(正确率), "feedback": "中文评语"}。"""

DELIVER_GENERATE_PROMPT = """你是交付验收设计者。为实操/项目任务写 2-5 条明确、可检验的验收标准。
只输出 JSON：{"acceptance_criteria": "标准文本"}。"""

GRADE_DELIVER_PROMPT = """你是交付验收评审员。依据验收标准判断用户提交的成果描述是否达标。
返回 JSON：{"score": 0-1(达标度), "feedback": "中文评审意见"}。score>=0.7 表示达标。"""


def _parse(client, system_prompt, user_prompt, output_model, max_tokens=4000):
    client = client or anthropic.Anthropic()
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=output_model,
    )
    if response.parsed_output is None:
        raise RuntimeError("LLM 输出解析失败")
    return response.parsed_output


def generate_test(task_title: str, task_description: str, client=None) -> TestContent:
    return _parse(
        client, TEST_GENERATE_PROMPT,
        f"任务：{task_title}\n内容：{task_description or '无'}",
        TestContent,
    )


def grade_test(
    task_title: str, task_description: str, content: TestContent, answers: dict, client=None
) -> GradeResult:
    payload = {
        "任务": task_title,
        "内容": task_description or "无",
        "题目": [q.model_dump() for q in content.questions],
        "用户答案": answers,
    }
    return _parse(
        client, GRADE_TEST_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        GradeResult,
    )


def generate_deliver_criteria(task_title: str, task_description: str, client=None) -> DeliverContent:
    return _parse(
        client, DELIVER_GENERATE_PROMPT,
        f"任务：{task_title}\n内容：{task_description or '无'}",
        DeliverContent,
    )


def grade_delivery(
    task_title: str, task_description: str, criteria: str, submission: str, client=None
) -> GradeResult:
    payload = {
        "任务": task_title,
        "内容": task_description or "无",
        "验收标准": criteria,
        "用户提交": submission,
    }
    return _parse(
        client, GRADE_DELIVER_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        GradeResult,
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_verifier.py -v`
Expected: `4 passed`

- [ ] **Step 5: 提交**

```bash
git add backend/app/llm/verifier.py backend/tests/test_verifier.py
git commit -m "feat: llm verification module for test and deliver modes"
```

---

### Task 8: Tasks API(勾选完成 + 检验流程)

**Files:**
- Create: `backend/app/api/tasks.py`
- Modify: `backend/app/main.py`(注册 tasks router)
- Create: `backend/tests/test_tasks_api.py`

**Interfaces:**
- Consumes: `get_db`、ORM 模型、`verifier` 四函数、`GradeResult`
- Produces:
  - `PATCH /api/tasks/{id}` body `{completed: bool}` → 更新任务状态 + 刷新所在里程碑状态 → 返回任务序列化
  - `GET /api/tasks/{id}/verification` → 按 `task.type` 生成内容(learn→测试,其余→交付),落一条草稿 `VerificationRecord`,返回 `{mode, content, record_id}`
  - `POST /api/tasks/{id}/verification` body `{record_id, answers?, submission?}` → 用草稿记录的内容判分,`score>=0.7` 则标记 task 已检验并完成,更新记录,返回 `{passed, score, feedback, verified}`
- 检验通过阈值 `PASS_THRESHOLD = 0.7` 常量在模块内定义

- [ ] **Step 1: 写路由模块**

`backend/app/api/tasks.py`:
```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..llm.verifier import (
    DeliverContent,
    TestContent,
    generate_deliver_criteria,
    generate_test,
    grade_delivery,
    grade_test,
)
from ..models import Milestone, Task, VerificationRecord
from .goals import serialize_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

PASS_THRESHOLD = 0.7


class TaskComplete(BaseModel):
    completed: bool


class VerificationSubmit(BaseModel):
    record_id: int
    answers: dict | None = None
    submission: str | None = None


def _refresh_milestone(milestone: Milestone) -> None:
    tasks = milestone.tasks
    done = [t for t in tasks if t.status == "done"]
    if tasks and len(done) == len(tasks):
        milestone.status = "done"
    elif done:
        milestone.status = "active"
    else:
        milestone.status = "todo"


@router.patch("/{task_id}")
def set_complete(task_id: int, payload: TaskComplete, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if payload.completed:
        task.status = "done"
        task.completed_at = task.completed_at or datetime.now()
    else:
        task.status = "todo"
        task.completed_at = None
    _refresh_milestone(task.milestone)
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.get("/{task_id}/verification")
def start_verification(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.type == "learn":
        content = generate_test(task.title, task.description)
        mode = "test"
    else:
        content = generate_deliver_criteria(task.title, task.description)
        mode = "deliver"
    record = VerificationRecord(
        task_id=task.id, mode=mode, content=content.model_dump_json(),
        submission="", result="", passed=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"mode": mode, "record_id": record.id, "content": content.model_dump()}


@router.post("/{task_id}/verification")
def submit_verification(
    task_id: int, payload: VerificationSubmit, db: Session = Depends(get_db)
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    record = db.get(VerificationRecord, payload.record_id)
    if not record or record.task_id != task.id:
        raise HTTPException(status_code=400, detail="检验记录不存在")

    if record.mode == "test":
        if payload.answers is None:
            raise HTTPException(status_code=400, detail="测试模式需提交 answers")
        content = TestContent.model_validate_json(record.content)
        grade = grade_test(task.title, task.description, content, payload.answers)
        record.submission = str(payload.answers)
    else:
        if payload.submission is None:
            raise HTTPException(status_code=400, detail="交付模式需提交 submission")
        criteria = DeliverContent.model_validate_json(record.content).acceptance_criteria
        grade = grade_delivery(task.title, task.description, criteria, payload.submission)
        record.submission = payload.submission

    passed = grade.score >= PASS_THRESHOLD
    record.result = grade.model_dump_json()
    record.passed = passed
    if passed:
        task.verified = True
        task.status = "done"
        task.completed_at = task.completed_at or datetime.now()
        _refresh_milestone(task.milestone)
    db.commit()
    return {"passed": passed, "score": grade.score, "feedback": grade.feedback, "verified": task.verified}
```

- [ ] **Step 2: 注册 tasks router**

`backend/app/main.py` 中 `app.include_router(goals.router)` 之后加:
```python
app.include_router(tasks.router)
```

- [ ] **Step 3: 写 API 测试**

`backend/tests/test_tasks_api.py`:
```python
from app.llm.verifier import DeliverContent, GradeResult, TestContent
from app.models import Goal, Milestone, Plan, Task, VerificationRecord


def _build_task(db_session, task_type="learn"):
    goal = Goal(title="目标")
    db_session.add(goal)
    plan = Plan(goal_id=0, strategy="s")
    goal.plan = plan
    ms = Milestone(title="M", order=1)
    plan.milestones.append(ms)
    t = Task(title="任务", type=task_type, order=0, effort=1.0)
    ms.tasks.append(t)
    db_session.commit()
    return t


def test_set_complete_updates_milestone(client, db_session):
    task = _build_task(db_session)
    res = client.patch(f"/api/tasks/{task.id}", json={"completed": True})
    assert res.status_code == 200
    db_session.refresh(task)
    assert task.status == "done"
    assert task.milestone.status == "done"


def test_verification_test_flow(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")

    def fake_generate_test(title, desc, client=None):
        return TestContent(questions=[
            {"id": 1, "type": "choice", "text": "Q", "options": ["a", "b"]},
        ])

    def fake_grade_test(title, desc, content, answers, client=None):
        return GradeResult(score=0.9, feedback="通过")

    monkeypatch.setattr("app.api.tasks.generate_test", fake_generate_test)
    monkeypatch.setattr("app.api.tasks.grade_test", fake_grade_test)

    start = client.get(f"/api/tasks/{task.id}/verification").json()
    assert start["mode"] == "test"
    record_id = start["record_id"]

    res = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": record_id, "answers": {"1": "a"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["passed"] is True
    assert body["verified"] is True
    db_session.refresh(task)
    assert task.verified is True
    assert task.status == "done"
    assert len(task.verifications) == 1
    assert task.verifications[0].passed is True


def test_verification_deliver_flow(client, db_session, monkeypatch):
    task = _build_task(db_session, "project")

    monkeypatch.setattr(
        "app.api.tasks.generate_deliver_criteria",
        lambda title, desc, client=None: DeliverContent(acceptance_criteria="标准"),
    )
    monkeypatch.setattr(
        "app.api.tasks.grade_delivery",
        lambda title, desc, criteria, submission, client=None: GradeResult(score=0.5, feedback="不达标"),
    )

    start = client.get(f"/api/tasks/{task.id}/verification").json()
    assert start["mode"] == "deliver"
    res = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": start["record_id"], "submission": "成果"},
    )
    body = res.json()
    assert body["passed"] is False
    assert body["verified"] is False


def test_verification_wrong_record(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")
    res = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": 999, "answers": {}},
    )
    assert res.status_code == 400
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_tasks_api.py -v`
Expected: `4 passed`

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/tasks.py backend/app/main.py backend/tests/test_tasks_api.py
git commit -m "feat: tasks api with completion toggle and verification flow"
```

---

### Task 9: 前端脚手架 + 暗黑主题 + API client

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: `src/types.ts` 的 `GoalDTO` / `PlanDTO` / `MilestoneDTO` / `TaskDTO` / `VerificationStart` / `VerificationSubmit` / `VerificationResult`
- Produces: `src/api/client.ts` 的 `api` 对象:`createGoal` / `listGoals` / `getGoal` / `deleteGoal` / `setTaskCompleted` / `getVerification` / `submitVerification`

- [ ] **Step 1: 写 package.json 与配置**

`frontend/package.json`:
```json
{
  "name": "planagent-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

`frontend/vite.config.ts`:
```ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PlanAgent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: 写全局样式(暗黑主题)**

`frontend/src/index.css`:
```css
:root {
  --bg: #000000;
  --card: #1a1a1a;
  --border: #2e2e2e;
  --accent: #e5e5e5;
  --text: #e5e5e5;
  --text-dim: #a3a3a3;
  --text-faint: #737373;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
}

a { color: inherit; text-decoration: none; }

button { cursor: pointer; }

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
}

.btn {
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 6px;
  padding: 9px 22px;
  font-weight: 600;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-ghost {
  background: var(--card);
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 10px;
}

.input {
  width: 100%;
  background: #0a0a0a;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--text);
}

.dim { color: var(--text-dim); }
.faint { color: var(--text-faint); }
```

- [ ] **Step 3: 写类型与 API client**

`frontend/src/types.ts`:
```ts
export type TaskType = 'learn' | 'practice' | 'project'

export interface TaskDTO {
  id: number
  title: string
  description: string
  type: TaskType
  scheduled_date: string | null
  effort: number
  order: number
  status: 'todo' | 'done'
  verified: boolean
  completed_at: string | null
}

export interface MilestoneDTO {
  id: number
  title: string
  description: string
  order: number
  due_date: string | null
  status: 'todo' | 'active' | 'done'
  tasks: TaskDTO[]
}

export interface PlanDTO {
  id: number
  strategy: string
  status: string
  milestones: MilestoneDTO[]
}

export interface GoalDTO {
  id: number
  title: string
  description: string
  target_date: string | null
  created_at: string
  plan?: PlanDTO
}

export interface TestQuestionDTO {
  id: number
  type: 'choice' | 'short'
  text: string
  options: string[]
}

export interface TestContentDTO { questions: TestQuestionDTO[] }
export interface DeliverContentDTO { acceptance_criteria: string }

export interface VerificationStart {
  mode: 'test' | 'deliver'
  record_id: number
  content: TestContentDTO | DeliverContentDTO
}

export interface VerificationSubmit {
  record_id: number
  answers?: Record<number, string>
  submission?: string
}

export interface VerificationResult {
  passed: boolean
  score: number
  feedback: string
  verified: boolean
}
```

`frontend/src/api/client.ts`:
```ts
import type {
  GoalDTO, TaskDTO, VerificationResult, VerificationStart, VerificationSubmit,
} from '../types'

const BASE = '/api'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* keep default */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  createGoal: (body: { title: string; description?: string; target_date?: string | null }) =>
    req<GoalDTO>('/goals', { method: 'POST', body: JSON.stringify(body) }),
  listGoals: () => req<GoalDTO[]>('/goals'),
  getGoal: (id: number) => req<GoalDTO>(`/goals/${id}`),
  deleteGoal: (id: number) => req<{ ok: boolean }>(`/goals/${id}`, { method: 'DELETE' }),
  setTaskCompleted: (id: number, completed: boolean) =>
    req<TaskDTO>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify({ completed }) }),
  getVerification: (taskId: number) =>
    req<VerificationStart>(`/tasks/${taskId}/verification`),
  submitVerification: (taskId: number, body: VerificationSubmit) =>
    req<VerificationResult>(`/tasks/${taskId}/verification`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
```

- [ ] **Step 4: 写入口 + 路由骨架**

`frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
```

`frontend/src/router.tsx`:
```tsx
import { createBrowserRouter } from 'react-router-dom'
import { GoalInput } from './pages/GoalInput'
import { PlanOverview } from './pages/PlanOverview'
import { DailyTasks } from './pages/DailyTasks'

export const router = createBrowserRouter([
  { path: '/', element: <GoalInput /> },
  { path: '/goals/:id', element: <PlanOverview /> },
  { path: '/goals/:id/daily', element: <DailyTasks /> },
])
```

- [ ] **Step 5: 安装并构建检查**

Run: `cd frontend && npm install && npm run build`
Expected: `tsc` 通过、Vite 构建成功。(三个页面文件尚不存在,先建最小占位再构建,或把 build 检查留到页面任务之后;推荐在此步只做 `npm install` + `tsc --noEmit` 前的占位页面。若占位,创建空的 `pages/` 三文件,内容后续 Task 覆盖。)

- [ ] **Step 6: 提交**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig*.json frontend/index.html frontend/src
git commit -m "feat: frontend scaffold with dark theme and api client"
```

---

### Task 10: 目标输入页

**Files:**
- Create: `frontend/src/pages/GoalInput.tsx`
- Create: `frontend/src/components/GoalList.tsx`

**Interfaces:**
- Consumes: `api.createGoal` / `api.listGoals` / `api.deleteGoal`,`GoalDTO`
- Produces: 页面路由 `/` —— 目标输入表单(标题必填、说明可选、目标日期可选)+ 已创建目标列表;提交成功跳转 `/goals/{id}`

- [ ] **Step 1: 写页面组件**

`frontend/src/pages/GoalInput.tsx`:
```tsx
import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO } from '../types'
import { GoalList } from '../components/GoalList'

export function GoalInput() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [goals, setGoals] = useState<GoalDTO[]>([])

  const loadGoals = () => api.listGoals().then(setGoals).catch(() => setGoals([]))
  useEffect(() => { void loadGoals() }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    setLoading(true)
    setError('')
    try {
      const goal = await api.createGoal({
        title: title.trim(),
        description: description.trim(),
        target_date: targetDate || null,
      })
      navigate(`/goals/${goal.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: '40px auto', padding: '0 16px' }}>
      <h1 style={{ fontSize: 24 }}>PlanAgent</h1>
      <p className="dim">输入一个目标，AI 会把它拆解成里程碑和每日任务。</p>

      <form className="card" style={{ padding: 20, marginTop: 16 }} onSubmit={onSubmit}>
        <label className="dim" style={{ fontSize: 13 }}>目标标题 *</label>
        <input
          className="input" style={{ marginTop: 6 }}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="例如：3个月从零学会Python编程"
        />
        <label className="dim" style={{ fontSize: 13, display: 'block', marginTop: 14 }}>补充说明(可选)</label>
        <textarea
          className="input" style={{ marginTop: 6, minHeight: 64 }}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="想达到什么程度？有什么约束？"
        />
        <label className="dim" style={{ fontSize: 13, display: 'block', marginTop: 14 }}>目标完成日期(可选)</label>
        <input
          type="date" className="input" style={{ marginTop: 6 }}
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
        />
        {error && <p style={{ color: '#f87171', fontSize: 13, marginTop: 10 }}>{error}</p>}
        <button className="btn" disabled={loading} style={{ marginTop: 18 }}>
          {loading ? 'AI 正在拆解计划…' : '生成计划'}
        </button>
      </form>

      <GoalList goals={goals} onDelete={async (id) => { await api.deleteGoal(id); void loadGoals() }} />
    </div>
  )
}
```

- [ ] **Step 2: 写目标列表组件**

`frontend/src/components/GoalList.tsx`:
```tsx
import { Link } from 'react-router-dom'
import type { GoalDTO } from '../types'

export function GoalList({ goals, onDelete }: { goals: GoalDTO[]; onDelete: (id: number) => void }) {
  if (goals.length === 0) return null
  return (
    <div style={{ marginTop: 24 }}>
      <h2 className="dim" style={{ fontSize: 15 }}>历史目标</h2>
      {goals.map((g) => (
        <div key={g.id} className="card" style={{ padding: 14, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Link to={`/goals/${g.id}`} style={{ fontWeight: 600 }}>{g.title}</Link>
          <button className="btn-ghost" onClick={() => onDelete(g.id)}>删除</button>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: 运行 dev server 验证**

Run: 后端在 `:8000` 运行、前端 `cd frontend && npm run dev`;浏览器打开 `http://localhost:5173`。
Expected: 页面为黑灰主题;输入标题点"生成计划",若未配 API key 则显示错误提示(可接受,后端调用验证放到集成阶段)。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/GoalInput.tsx frontend/src/components/GoalList.tsx
git commit -m "feat: goal input page"
```

---

### Task 11: 计划总览页

**Files:**
- Create: `frontend/src/pages/PlanOverview.tsx`
- Create: `frontend/src/components/ProgressBar.tsx`

**Interfaces:**
- Consumes: `api.getGoal`,路由参数 `:id`,`GoalDTO`/`PlanDTO`/`MilestoneDTO`
- Produces: 页面 `/goals/:id` —— 标题、整体进度条(`已完成 x / y 任务`)、策略摘要、里程碑卡片(标题/说明/日期范围/状态徽章/可展开任务列表)、"每日任务"入口链接

- [ ] **Step 1: 写进度条组件**

`frontend/src/components/ProgressBar.tsx`:
```tsx
export function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100)
  return (
    <div>
      <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>
        整体进度 · 已完成 {done} / {total} 个任务
      </div>
      <div style={{ background: 'var(--border)', borderRadius: 4, height: 8 }}>
        <div style={{ background: 'var(--accent)', borderRadius: 4, height: 8, width: `${pct}%` }} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 写总览页**

`frontend/src/pages/PlanOverview.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, MilestoneDTO } from '../types'
import { ProgressBar } from '../components/ProgressBar'

const STATUS_TEXT: Record<string, string> = { todo: '未开始', active: '进行中', done: '已完成' }

function allTasks(plan?: GoalDTO['plan']): Array<{ status: string }> {
  return plan ? plan.milestones.flatMap((m) => m.tasks) : []
}

export function PlanOverview() {
  const { id } = useParams()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  }, [id])

  if (error) return <p style={{ color: '#f87171' }}>{error}</p>
  if (!goal || !goal.plan) return <p className="faint">加载中…</p>

  const tasks = allTasks(goal)
  const done = tasks.filter((t) => t.status === 'done').length

  return (
    <div style={{ maxWidth: 760, margin: '40px auto', padding: '0 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: 22 }}>{goal.title}</h1>
        <Link to={`/goals/${goal.id}/daily`} className="btn-ghost">每日任务 ›</Link>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <ProgressBar done={done} total={tasks.length} />
        <p className="dim" style={{ fontSize: 13, margin: '10px 0 0' }}>策略：{goal.plan.strategy}</p>
      </div>

      <div style={{ marginTop: 20 }}>
        {goal.plan.milestones.map((m) => <MilestoneCard key={m.id} m={m} />)}
      </div>
    </div>
  )
}

function MilestoneCard({ m }: { m: MilestoneDTO }) {
  const [open, setOpen] = useState(false)
  const done = m.tasks.filter((t) => t.status === 'done').length
  return (
    <div className="card" style={{ padding: 14, marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} onClick={() => setOpen(!open)}>
        <div>
          <span style={{ fontWeight: 600 }}>里程碑 {m.order} · {m.title}</span>
          <p className="faint" style={{ fontSize: 12, margin: '4px 0 0' }}>
            {m.description} · {done}/{m.tasks.length} 完成
          </p>
        </div>
        <span className="btn-ghost" style={{ borderRadius: 10, fontSize: 12 }}>
          {STATUS_TEXT[m.status] ?? m.status}
        </span>
      </div>
      {open && (
        <div style={{ marginTop: 10 }}>
          {m.tasks.map((t) => (
            <div key={t.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0', fontSize: 13 }}>
              <span style={{ color: t.status === 'done' ? 'var(--text-faint)' : 'var(--text)' }}>
                {t.status === 'done' ? '☑' : '☐'}
              </span>
              <span style={{ textDecoration: t.status === 'done' ? 'line-through' : 'none', color: t.status === 'done' ? 'var(--text-faint)' : 'var(--text)' }}>
                {t.title}
              </span>
              <span className="faint">{t.scheduled_date ?? ''}</span>
              {t.verified && <span className="btn-ghost" style={{ borderRadius: 10, fontSize: 11, padding: '1px 8px' }}>已验证</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 运行 dev server 验证**

Run: 打开 `http://localhost:5173/goals/1`(有数据时)。Expected: 黑灰主题、进度条、里程碑卡片可展开。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/PlanOverview.tsx frontend/src/components/ProgressBar.tsx
git commit -m "feat: plan overview page"
```

---

### Task 12: 每日任务页(含月历)

**Files:**
- Create: `frontend/src/pages/DailyTasks.tsx`
- Create: `frontend/src/components/Calendar.tsx`
- Create: `frontend/src/components/VerificationModal.tsx`(占位,Task 13 实现完整逻辑)

**Interfaces:**
- Consumes: `api.getGoal` / `api.setTaskCompleted`,`GoalDTO`
- Produces: 页面 `/goals/:id/daily` —— 左:日期切换 + 当日任务列表(勾选圆点、已完成删除线、类型标签、"去检验"按钮);右:月历(有任务的日子白点、今天描边、选中白底)

- [ ] **Step 1: 写月历组件**

`frontend/src/components/Calendar.tsx`:
```tsx
const WEEK = ['日', '一', '二', '三', '四', '五', '六']

export function Calendar({
  year, month, selected, datesWithTasks, onSelect,
}: {
  year: number
  month: number // 0-11
  selected: string
  datesWithTasks: Set<string>
  onSelect: (iso: string) => void
}) {
  const first = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const todayIso = new Date().toISOString().slice(0, 10)
  const cells: Array<number | null> = [...Array(first).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]

  function prev() { onMonthChange(-1) }
  function next() { onMonthChange(1) }

  function onMonthChange(delta: number) {
    const d = new Date(year, month + delta, 1)
    onSelect(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`)
  }

  return (
    <div className="card" style={{ padding: 16, width: 250 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <button className="btn-ghost" onClick={prev}>‹</button>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{year}年{month + 1}月</span>
        <button className="btn-ghost" onClick={next}>›</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 2, marginBottom: 4 }}>
        {WEEK.map((w) => <span key={w} style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-faint)' }}>{w}</span>)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 2 }}>
        {cells.map((day, i) => {
          if (day === null) return <div key={`b${i}`} />
          const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const isSel = iso === selected
          const isToday = iso === todayIso
          const hasTasks = datesWithTasks.has(iso)
          return (
            <div
              key={iso}
              onClick={() => onSelect(iso)}
              style={{
                width: 28, height: 28, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', fontSize: 12, borderRadius: 6, cursor: 'pointer',
                background: isSel ? 'var(--accent)' : undefined,
                color: isSel ? '#000' : hasTasks ? 'var(--text)' : 'var(--text-faint)',
                border: isToday ? '1px solid var(--text-faint)' : undefined,
              }}
            >
              {day}
              {hasTasks && !isSel && <span style={{ width: 4, height: 4, background: 'var(--accent)', borderRadius: 2 }} />}
            </div>
          )
        })}
      </div>
      <p className="faint" style={{ fontSize: 11, marginTop: 10 }}>• = 当天有任务</p>
    </div>
  )
}
```

- [ ] **Step 2: 写每日任务页**

`frontend/src/pages/DailyTasks.tsx`:
```tsx
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, TaskDTO } from '../types'
import { Calendar } from '../components/Calendar'
import { VerificationModal } from '../components/VerificationModal'

const TYPE_TEXT: Record<string, string> = { learn: '学习', practice: '实操', project: '项目' }

function toKey(iso: string | null): string {
  return iso ? iso.slice(0, 10) : '未排期'
}

export function DailyTasks() {
  const { id } = useParams()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [selected, setSelected] = useState(() => new Date().toISOString().slice(0, 10))
  const [verifyTask, setVerifyTask] = useState<TaskDTO | null>(null)

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch(() => undefined)
  }, [id])

  const tasks = useMemo(() => (goal?.plan ? goal.plan.milestones.flatMap((m) => m.tasks) : []), [goal])
  const datesWithTasks = useMemo(
    () => new Set(tasks.map((t) => toKey(t.scheduled_date))),
    [tasks],
  )
  const dayTasks = useMemo(
    () => tasks.filter((t) => toKey(t.scheduled_date) === selected).sort((a, b) => a.order - b.order),
    [tasks, selected],
  )

  async function toggle(task: TaskDTO) {
    const updated = await api.setTaskCompleted(task.id, task.status !== 'done')
    setGoal((g) => (g ? {
      ...g,
      plan: {
        ...g.plan!,
        milestones: g.plan!.milestones.map((m) => ({
          ...m,
          tasks: m.tasks.map((t) => (t.id === updated.id ? updated : t)),
        })),
      },
    } : g))
  }

  if (!goal || !goal.plan) return <p className="faint">加载中…</p>

  return (
    <div style={{ maxWidth: 760, margin: '40px auto', padding: '0 16px' }}>
      <Link to={`/goals/${goal.id}`} className="btn-ghost">‹ 返回总览</Link>
      <h1 style={{ fontSize: 22 }}>{goal.title}</h1>

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginTop: 16, flexWrap: 'wrap' }}>
        <div className="card" style={{ padding: 16, flex: 1, minWidth: 300 }}>
          <div style={{ textAlign: 'center', marginBottom: 12 }}>
            <div style={{ fontWeight: 600 }}>{selected}</div>
            <div className="faint" style={{ fontSize: 12 }}>点击任务左侧圆点可勾选完成</div>
          </div>
          {dayTasks.length === 0 && <p className="faint" style={{ textAlign: 'center' }}>这一天没有任务</p>}
          {dayTasks.map((t) => (
            <div key={t.id} className="card" style={{ padding: '10px 12px', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                onClick={() => void toggle(t)}
                style={{
                  width: 18, height: 18, borderRadius: '50%', flexShrink: 0, cursor: 'pointer',
                  background: t.status === 'done' ? 'var(--accent)' : 'transparent',
                  border: `2px solid ${t.status === 'done' ? 'var(--accent)' : 'var(--text-faint)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, color: '#000',
                }}
              >
                {t.status === 'done' ? '✓' : ''}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, textDecoration: t.status === 'done' ? 'line-through' : 'none', color: t.status === 'done' ? 'var(--text-faint)' : 'var(--text)' }}>
                  {t.title}
                </div>
                <div className="faint" style={{ fontSize: 11, marginTop: 2 }}>
                  {TYPE_TEXT[t.type] ?? t.type} · 约 {t.effort} 小时
                  {t.verified ? ' · 已验证' : ''}
                </div>
              </div>
              <button className="btn-ghost" onClick={() => setVerifyTask(t)}>去检验</button>
            </div>
          ))}
        </div>

        <Calendar
          year={Number(selected.slice(0, 4))}
          month={Number(selected.slice(5, 7)) - 1}
          selected={selected}
          datesWithTasks={datesWithTasks}
          onSelect={setSelected}
        />
      </div>

      {verifyTask && <VerificationModal task={verifyTask} onClose={() => setVerifyTask(null)} />}
    </div>
  )
}
```

- [ ] **Step 3: 写 VerificationModal 占位(完整逻辑 Task 13 覆盖)**

`frontend/src/components/VerificationModal.tsx`:
```tsx
import type { TaskDTO } from '../types'

export function VerificationModal({ task, onClose }: { task: TaskDTO; onClose: () => void }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }} onClick={onClose}>
      <div className="card" style={{ padding: 20, width: 400 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>检验 · {task.title}</strong>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <p className="faint">加载检验内容中…</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 运行 dev server 验证**

Run: 打开 `http://localhost:5173/goals/1/daily`。Expected: 左任务列表 + 右月历,黑灰主题。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/DailyTasks.tsx frontend/src/components/Calendar.tsx frontend/src/components/VerificationModal.tsx
git commit -m "feat: daily tasks page with calendar"
```

---

### Task 13: 检验区弹窗

**Files:**
- Modify: `frontend/src/components/VerificationModal.tsx`(替换占位为完整实现)

**Interfaces:**
- Consumes: `api.getVerification` / `api.submitVerification`,`TaskDTO`,`VerificationStart` / `VerificationSubmit` / `VerificationResult`
- Produces: 深色弹窗 —— 测试模式:选择题(可点选)+ 简答题(输入框),提交后显示分数/反馈/通过与否;交付模式:显示验收标准 + 文本域,提交后显示评审结果;完成后父组件刷新任务数据(通过 `onVerified` 回调)。

- [ ] **Step 1: 写完整检验弹窗**

`frontend/src/components/VerificationModal.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  DeliverContentDTO, TaskDTO, TestContentDTO, VerificationResult,
} from '../types'

export function VerificationModal({
  task, onClose, onVerified,
}: { task: TaskDTO; onClose: () => void; onVerified?: (result: VerificationResult) => void }) {
  const [mode, setMode] = useState<'test' | 'deliver'>('test')
  const [recordId, setRecordId] = useState(0)
  const [content, setContent] = useState<TestContentDTO | DeliverContentDTO | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [submission, setSubmission] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getVerification(task.id)
      .then((start) => { setMode(start.mode); setRecordId(start.record_id); setContent(start.content) })
      .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  }, [task.id])

  async function submit() {
    setLoading(true)
    setError('')
    try {
      const body = mode === 'test'
        ? { record_id: recordId, answers }
        : { record_id: recordId, submission }
      const res = await api.submitVerification(task.id, body)
      setResult(res)
      onVerified?.(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setLoading(false)
    }
  }

  const testContent = mode === 'test' ? content as TestContentDTO : null
  const deliverContent = mode === 'deliver' ? content as DeliverContentDTO : null

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }} onClick={onClose}>
      <div className="card" style={{ padding: 20, width: 460, maxHeight: '80vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>检验 · {task.title}</strong>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <p className="faint" style={{ fontSize: 12, margin: '6px 0 14px' }}>
          {mode === 'test' ? '测试模式 · 答对 70% 即通过' : '交付模式 · 提交成果描述，评审是否达标'}
        </p>

        {error && <p style={{ color: '#f87171', fontSize: 13 }}>{error}</p>}

        {result ? (
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
              {result.passed ? '✓ 检验通过' : '✗ 未通过'}
            </div>
            <div className="dim" style={{ fontSize: 13, marginBottom: 8 }}>得分：{Math.round(result.score * 100)}%</div>
            <p style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{result.feedback}</p>
            <button className="btn" style={{ marginTop: 16 }} onClick={onClose}>关闭</button>
          </div>
        ) : (
          <>
            {testContent && testContent.questions.map((q) => (
              <div key={q.id} style={{ marginBottom: 14 }}>
                <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>{q.text}</p>
                {q.type === 'choice' ? (
                  q.options.map((opt) => (
                    <label key={opt} style={{ display: 'block', fontSize: 13, padding: '2px 0', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name={`q${q.id}`}
                        checked={answers[q.id] === opt}
                        onChange={() => setAnswers({ ...answers, [q.id]: opt })}
                      /> {opt}
                    </label>
                  ))
                ) : (
                  <textarea
                    className="input" style={{ minHeight: 56 }}
                    value={answers[q.id] ?? ''}
                    onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                  />
                )}
              </div>
            ))}
            {deliverContent && (
              <div>
                <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>验收标准</p>
                <p className="dim" style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{deliverContent.acceptance_criteria}</p>
                <textarea
                  className="input" style={{ minHeight: 80, marginTop: 10 }}
                  placeholder="填写你的实现成果 / 代码链接 / 说明……"
                  value={submission}
                  onChange={(e) => setSubmission(e.target.value)}
                />
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn-ghost" onClick={onClose}>取消</button>
              <button className="btn" disabled={loading} onClick={() => void submit()}>
                {loading ? 'AI 评审中…' : mode === 'test' ? '提交检验' : '提交评审'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 接线 onVerified 回调**

`frontend/src/pages/DailyTasks.tsx` 中 `<VerificationModal task={verifyTask} onClose={() => setVerifyTask(null)} />` 改为传入 `onVerified`,使弹窗关闭时刷新任务数据:
```tsx
<VerificationModal
  task={verifyTask}
  onClose={() => setVerifyTask(null)}
  onVerified={() => {
    if (id) api.getGoal(Number(id)).then(setGoal).catch(() => undefined)
  }}
/>
```

- [ ] **Step 3: 运行验证**

Run: 打开每日页,点"去检验",Expected: 深色弹窗出现测试题(learn 任务)或验收标准(实操/项目任务);提交后显示评审结果。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/VerificationModal.tsx frontend/src/pages/DailyTasks.tsx
git commit -m "feat: verification modal with test and deliver modes"
```

---

### Task 14: 集成与收尾

**Files:**
- Create: `frontend/.gitignore`
- Create: `.gitignore`(项目根)
- Create: `README.md`(项目根)
- Modify: `frontend/package.json`(如有必要)

**Interfaces:**
- 无新接口;验证端到端流程可用。

- [ ] **Step 1: 写 .gitignore 与 README**

项目根 `.gitignore`:
```
__pycache__/
*.pyc
.venv/
*.db
node_modules/
dist/
.superpowers/
```

`frontend/.gitignore`:
```
node_modules/
dist/
```

`README.md`:
```markdown
# PlanAgent

目标驱动的规划 Web 应用：输入一个目标，AI 拆解成里程碑和每日任务，排程算法排出日程，支持勾选完成与「去检验」验证。

## 运行

### 后端
```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (已代理 /api 到 :8000)
```

## 测试
```bash
cd backend && python -m pytest
```

## 结构
- `backend/app/llm` — LLM 编排(计划生成、检验出题/判分)
- `backend/app/scheduler` — 确定性排程算法
- `backend/app/services` — 计划生成服务(LLM+排程+落库)
- `backend/app/api` — REST 路由
- `frontend/src` — React 前端
```

- [ ] **Step 2: 端到端手动验证**

Run:
1. `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
2. 配好 `ANTHROPIC_API_KEY`
3. `cd frontend && npm run dev`
4. 浏览器打开 `http://localhost:5173`,依次验证:
   - 输入目标"3个月从零学会Python"→ 生成计划 → 跳转总览页,显示进度条、策略、里程碑
   - 进入每日任务页,日历有任务标记,勾选一个任务 → 圆点变白勾
   - 对一个 learn 任务点"去检验" → 作答提交 → 显示通过/未通过
   - 刷新页面数据仍在(SQLite 持久化)

- [ ] **Step 3: 提交**

```bash
git add .gitignore frontend/.gitignore README.md
git commit -m "docs: add readme and gitignore; complete integration"
```

---

## Self-Review 记录

- **Spec 覆盖**:§3 架构(backend/frontend 分离)→ Task 1/9;§4 数据模型 → Task 2;§5 LLM+排程 → Task 3/4/5;§6 API → Task 6/8;§7 前端三视图+配色+检验区 → Task 10-13;§8 错误处理 → 各 API 层 502/404/400;§9 测试 → 各 Task 测试。动态重规划/多用户属 spec 后续迭代,不在本计划。
- **占位扫描**:无 TBD;检验流程(出题→提交→判分→verified→VerificationRecord)在 Task 7/8 全实现。
- **类型一致性**:`schedule(plan_spec, start_date, blocks_per_day, hours_per_block)`、`generate_plan(title, description, target_date, client=None)`、`create_goal_with_plan(db, title, description, target_date)`、`grade_test/grade_delivery` 返回值 `GradeResult(score, feedback)` 在各任务间一致;`PASS_THRESHOLD=0.7` 由 API 层计算 passed。
