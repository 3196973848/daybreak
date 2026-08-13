# Task 3: 排程算法(纯函数)

## 目标

实现确定性排程算法 `schedule()`,把 LLM 输出的 PlanSpec 铺到具体日期;写三个单元测试(TDD)。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 3** 一节。

## 要创建的文件

- `backend/app/llm/__init__.py`(空包)
- `backend/app/llm/schema.py`
- `backend/app/scheduler/__init__.py`(空包)
- `backend/app/scheduler/scheduler.py`
- `backend/tests/test_scheduler.py`

## 关键接口(后续任务依赖,必须一致)

```python
# app/llm/schema.py
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

```python
# app/scheduler/scheduler.py
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

### `backend/tests/test_scheduler.py`

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

## 完成标准

1. 先写测试确认失败(ModuleNotFoundError)→ 再实现 → `cd backend && python -m pytest tests/test_scheduler.py -v` → `3 passed`
2. 创建 git commit(`feat: deterministic scheduler pure function`)
3. 报告:提交 hash、测试摘要、concerns

## 提交命令

```bash
git add backend/app/llm backend/app/scheduler backend/tests/test_scheduler.py
git commit -m "feat: deterministic scheduler pure function"
```

## 报告

<!-- Codex: 完成后在此填写 -->
