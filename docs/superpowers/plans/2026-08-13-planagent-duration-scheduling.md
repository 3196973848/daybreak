# PlanAgent Duration-Based Uniform Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the absolute completion-date field with a numeric day/week/month duration and distribute all generated tasks uniformly from the server's current date through the computed deadline, including weekends.

**Architecture:** A new pure duration helper converts relative durations to absolute dates, including calendar-month clamping. The existing scheduler gains an optional `end_date`; when present it follows a deterministic uniform branch, while the current capacity branch remains unchanged. The service resolves one start date, persists the computed target date, schedules tasks, and derives milestone dates; the API validates mutually exclusive legacy/new inputs. The React form submits only duration fields and is covered by a focused interaction test.

**Tech Stack:** Python 3.10, FastAPI, Pydantic 2, SQLAlchemy 2, pytest 9, React 18, TypeScript 5, Vite 5, Vitest 2, Testing Library.

## Global Constraints

- The approved design is `docs/superpowers/specs/2026-08-13-planagent-duration-scheduling-design.md`.
- LLM output continues to contain content and ordering only; all dates are calculated by deterministic server code.
- Duration units are exactly `day`, `week`, and `month`; values are positive integers.
- Uniform scheduling includes weekends, preserves task order, puts the first task on the start date, and puts the final task on the deadline.
- Legacy `target_date` requests remain supported; requests without any deadline retain the existing capacity scheduler.
- The new duration fields and legacy `target_date` are mutually exclusive.
- Do not modify or add database columns: the resolved absolute deadline remains in `Goal.target_date`.
- Backend verification runs from `backend/` with `D:\conda\envs\dl2025\python.exe -m pytest`; frontend verification runs from `frontend/` with `npm test` and `npm run build`.

## File Structure

- Create `backend/app/scheduler/duration.py`: relative-duration type and calendar arithmetic.
- Modify `backend/app/scheduler/scheduler.py`: optional uniform scheduling branch.
- Modify `backend/app/services/planner_service.py`: resolve one start/deadline pair, persist it, and derive milestone dates.
- Modify `backend/app/api/goals.py`: request validation and forwarding of duration fields.
- Modify `backend/tests/test_scheduler.py`: pure duration and uniform scheduling coverage.
- Modify `backend/tests/test_planner_service.py`: persistence and milestone due-date coverage.
- Modify `backend/tests/test_goals_api.py`: API contract and 422 validation coverage.
- Modify `frontend/src/api/client.ts`: typed duration payload.
- Modify `frontend/src/pages/GoalInput.tsx`: duration input/select UI.
- Modify `frontend/src/pages/DailyTasks.tsx`: stable completed-task checkmark markup.
- Modify `frontend/src/index.css`: duration control layout.
- Create `frontend/src/pages/GoalInput.test.tsx`: form/payload interaction test.
- Create `frontend/src/pages/DailyTasks.test.tsx`: completion toggle visual/interaction test.
- Modify `frontend/package.json`, `frontend/package-lock.json`, and `frontend/vite.config.ts`: frontend test tooling.

---

### Task 1: Pure Duration Arithmetic and Uniform Scheduler

**Files:**
- Create: `backend/app/scheduler/duration.py`
- Modify: `backend/app/scheduler/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Produces: `DurationUnit = Literal["day", "week", "month"]`.
- Produces: `calculate_target_date(start_date: date, value: int, unit: DurationUnit) -> date`.
- Extends: `schedule(plan, start_date, blocks_per_day=2, hours_per_block=1.0, end_date: date | None = None) -> list[ScheduledTask]`.
- Preserves: `ScheduledTask(milestone_index: int, task_index: int, date: date)` and the existing capacity behavior when `end_date is None`.

- [ ] **Step 1: Add failing duration-arithmetic tests**

Append these imports and tests to `backend/tests/test_scheduler.py`:

```python
import pytest

from app.scheduler.duration import calculate_target_date


@pytest.mark.parametrize(
    ("start", "value", "unit", "expected"),
    [
        (date(2026, 8, 13), 10, "day", date(2026, 8, 23)),
        (date(2026, 8, 13), 2, "week", date(2026, 8, 27)),
        (date(2026, 1, 31), 1, "month", date(2026, 2, 28)),
        (date(2024, 1, 31), 1, "month", date(2024, 2, 29)),
        (date(2026, 11, 30), 3, "month", date(2027, 2, 28)),
    ],
)
def test_calculate_target_date(start, value, unit, expected):
    assert calculate_target_date(start, value, unit) == expected


def test_calculate_target_date_rejects_non_positive_value():
    with pytest.raises(ValueError, match="duration_value 必须为正整数"):
        calculate_target_date(date(2026, 8, 13), 0, "day")
```

- [ ] **Step 2: Run the duration tests and verify RED**

Run:

```powershell
cd backend
D:\conda\envs\dl2025\python.exe -m pytest tests/test_scheduler.py::test_calculate_target_date tests/test_scheduler.py::test_calculate_target_date_rejects_non_positive_value -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.scheduler.duration'`.

- [ ] **Step 3: Implement calendar-safe duration conversion**

Create `backend/app/scheduler/duration.py`:

```python
import calendar
from datetime import date, timedelta
from typing import Literal

DurationUnit = Literal["day", "week", "month"]


def calculate_target_date(start_date: date, value: int, unit: DurationUnit) -> date:
    if value <= 0:
        raise ValueError("duration_value 必须为正整数")
    if unit == "day":
        return start_date + timedelta(days=value)
    if unit == "week":
        return start_date + timedelta(days=value * 7)
    if unit == "month":
        month_index = start_date.year * 12 + start_date.month - 1 + value
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(start_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    raise ValueError("duration_unit 必须为 day、week 或 month")
```

- [ ] **Step 4: Run the duration tests and verify GREEN**

Run the Step 2 command again. Expected: all six parameter/case executions pass.

- [ ] **Step 5: Add failing uniform-scheduling tests**

Append to `backend/tests/test_scheduler.py`:

```python
def test_uniform_schedule_spans_start_through_deadline_including_weekend():
    plan = _plan(
        TaskSpec(title="a"),
        TaskSpec(title="b"),
        TaskSpec(title="c"),
    )
    result = schedule(
        plan,
        date(2026, 8, 14),  # Friday
        end_date=date(2026, 8, 16),  # Sunday
    )
    assert [item.date for item in result] == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
    ]


def test_uniform_schedule_allows_multiple_tasks_on_same_day():
    plan = _plan(*(TaskSpec(title=str(i)) for i in range(5)))
    result = schedule(plan, date(2026, 8, 13), end_date=date(2026, 8, 15))
    assert [item.date for item in result] == [
        date(2026, 8, 13),
        date(2026, 8, 13),
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 15),
    ]


def test_uniform_schedule_single_task_starts_today():
    result = schedule(
        _plan(TaskSpec(title="only")),
        date(2026, 8, 13),
        end_date=date(2026, 9, 13),
    )
    assert [item.date for item in result] == [date(2026, 8, 13)]


def test_uniform_schedule_empty_plan_returns_empty():
    plan = PlanSpec(strategy="s", milestones=[])
    assert schedule(plan, date(2026, 8, 13), end_date=date(2026, 9, 13)) == []


def test_uniform_schedule_rejects_deadline_before_start():
    with pytest.raises(ValueError, match="target_date 不能早于计划开始日"):
        schedule(
            _plan(TaskSpec(title="a")),
            date(2026, 8, 13),
            end_date=date(2026, 8, 12),
        )
```

- [ ] **Step 6: Run the uniform tests and verify RED**

Run:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_scheduler.py -v
```

Expected: the new tests fail with `TypeError: schedule() got an unexpected keyword argument 'end_date'`; the three legacy capacity tests still pass.

- [ ] **Step 7: Add the deterministic uniform branch**

Replace `schedule()` in `backend/app/scheduler/scheduler.py` with:

```python
def schedule(
    plan: PlanSpec,
    start_date: date,
    blocks_per_day: int = 2,
    hours_per_block: float = 1.0,
    end_date: date | None = None,
) -> list[ScheduledTask]:
    if end_date is not None:
        if end_date < start_date:
            raise ValueError("target_date 不能早于计划开始日")
        task_keys = [
            (milestone_index, task_index)
            for milestone_index, milestone in enumerate(plan.milestones)
            for task_index, _ in enumerate(milestone.tasks)
        ]
        if not task_keys:
            return []
        if len(task_keys) == 1:
            milestone_index, task_index = task_keys[0]
            return [ScheduledTask(milestone_index, task_index, start_date)]
        span_days = (end_date - start_date).days
        last_index = len(task_keys) - 1
        return [
            ScheduledTask(
                milestone_index,
                task_index,
                start_date + timedelta(days=round(index * span_days / last_index)),
            )
            for index, (milestone_index, task_index) in enumerate(task_keys)
        ]

    if blocks_per_day <= 0 or hours_per_block <= 0:
        raise ValueError("blocks_per_day 与 hours_per_block 必须为正数")
    out: list[ScheduledTask] = []
    day = start_date
    blocks_left = blocks_per_day
    for mi, ms in enumerate(plan.milestones):
        for idx, task in enumerate(ms.tasks):
            needed = max(1, math.ceil(task.effort_hours / hours_per_block))
            if needed > blocks_left:
                day += timedelta(days=1)
                blocks_left = blocks_per_day
            out.append(ScheduledTask(mi, idx, day))
            blocks_left = max(0, blocks_left - needed)
    return out
```

- [ ] **Step 8: Verify scheduler tests and commit**

Run:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_scheduler.py -v
```

Expected: all legacy and new scheduler tests pass.

Commit:

```powershell
git add backend/app/scheduler/duration.py backend/app/scheduler/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: add duration-aware uniform scheduler"
```

---

### Task 2: Persisted Deadline, Milestone Dates, and Goals API Contract

**Files:**
- Modify: `backend/app/services/planner_service.py`
- Modify: `backend/app/api/goals.py`
- Modify: `backend/tests/test_planner_service.py`
- Modify: `backend/tests/test_goals_api.py`

**Interfaces:**
- Extends: `create_goal_with_plan(db, title, description="", target_date=None, duration_value=None, duration_unit=None) -> Goal`.
- Extends: `GoalCreate` with `duration_value: int | None` and `duration_unit: Literal["day", "week", "month"] | None`.
- Preserves: legacy `target_date` input and all existing serialized response fields.
- Consumes: Task 1 `calculate_target_date()` and `schedule(..., end_date=...)`.

- [ ] **Step 1: Add failing service tests for duration persistence and uniform milestone dates**

Add this fixture spec and tests to `backend/tests/test_planner_service.py`:

```python
def _three_task_spec():
    return PlanSpec(
        strategy="均匀学习",
        milestones=[
            MilestoneSpec(
                title="阶段一",
                order=1,
                target_date_offset_days=2,
                tasks=[TaskSpec(title="任务1"), TaskSpec(title="任务2")],
            ),
            MilestoneSpec(
                title="阶段二",
                order=2,
                target_date_offset_days=4,
                tasks=[TaskSpec(title="任务3")],
            ),
            MilestoneSpec(
                title="空阶段",
                order=3,
                target_date_offset_days=6,
                tasks=[],
            ),
        ],
    )


def test_duration_persists_deadline_and_uses_uniform_task_and_milestone_dates(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _three_task_spec()
    )
    start = date.today()
    goal = create_goal_with_plan(
        db_session,
        "目标",
        duration_value=10,
        duration_unit="day",
    )
    assert goal.target_date == start + timedelta(days=10)
    assert [task.scheduled_date for ms in goal.plan.milestones for task in ms.tasks] == [
        start,
        start + timedelta(days=5),
        start + timedelta(days=10),
    ]
    assert [ms.due_date for ms in goal.plan.milestones] == [
        start + timedelta(days=5),
        start + timedelta(days=10),
        start + timedelta(days=10),
    ]


def test_legacy_target_date_also_uses_uniform_schedule(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _three_task_spec()
    )
    start = date.today()
    target = start + timedelta(days=8)
    goal = create_goal_with_plan(db_session, "目标", target_date=target)
    assert [task.scheduled_date for ms in goal.plan.milestones for task in ms.tasks] == [
        start,
        start + timedelta(days=4),
        target,
    ]
```

Replace the existing `test_create_goal_persists_full_tree` with this no-deadline compatibility test:

```python
def test_create_goal_persists_full_tree(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _fake_spec()
    )
    goal = create_goal_with_plan(db_session, "目标", "说明")
    db_session.refresh(goal)
    assert goal.plan is not None
    ms = goal.plan.milestones[0]
    assert ms.title == "里程碑1"
    assert ms.due_date == date.today() + timedelta(days=7)
    assert len(ms.tasks) == 2
    assert ms.tasks[0].scheduled_date == date.today()
    assert ms.tasks[1].scheduled_date == date.today() + timedelta(days=1)
    assert ms.tasks[1].verified is False
```

- [ ] **Step 2: Run service tests and verify RED**

Run:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_planner_service.py -v
```

Expected: duration test fails because `create_goal_with_plan()` does not accept `duration_value`; legacy deadline test fails because current scheduling ignores `target_date`.

- [ ] **Step 3: Resolve one start date and persist the computed deadline in the service**

In `backend/app/services/planner_service.py`, import:

```python
from ..scheduler.duration import DurationUnit, calculate_target_date
```

Extend the signature:

```python
def create_goal_with_plan(
    db: Session,
    title: str,
    description: str = "",
    target_date: date | None = None,
    duration_value: int | None = None,
    duration_unit: DurationUnit | None = None,
) -> Goal:
```

Replace the initial Goal creation with:

```python
    start = date.today()
    if (duration_value is None) != (duration_unit is None):
        raise ValueError("duration_value 与 duration_unit 必须同时提供")
    if target_date is not None and duration_value is not None:
        raise ValueError("target_date 与预期完成时长不能同时提供")
    if duration_value is not None and duration_unit is not None:
        target_date = calculate_target_date(start, duration_value, duration_unit)
    if target_date is not None and target_date < start:
        raise ValueError("target_date 不能早于今天")

    goal = Goal(title=title, description=description, target_date=target_date)
```

Remove the later duplicate `start = date.today()` and pass the deadline into scheduling:

```python
scheduled = schedule(
    spec,
    start,
    blocks_per_day=settings.blocks_per_day,
    hours_per_block=settings.hours_per_block,
    end_date=target_date,
)
```

Before the milestone loop, build:

```python
dates_by_milestone = {
    milestone_index: [
        by_key[(milestone_index, task_index)]
        for task_index, _ in enumerate(ms.tasks)
    ]
    for milestone_index, ms in enumerate(spec.milestones)
}
```

Inside the milestone loop, replace the current due-date assignment with:

```python
if target_date is not None:
    milestone_dates = dates_by_milestone[mi]
    due = milestone_dates[-1] if milestone_dates else target_date
else:
    due = start + timedelta(days=ms.target_date_offset_days)
```

- [ ] **Step 4: Run service tests and verify GREEN**

Run the Step 2 command again. Expected: all planner-service tests pass.

- [ ] **Step 5: Add failing Goals API validation and forwarding tests**

Update the `fake` in `test_create_goal` to accept the new keyword arguments:

```python
def fake(db, title, description, target_date, duration_value=None, duration_unit=None):
    return _build_goal(db_session)
```

Add to `backend/tests/test_goals_api.py`:

```python
import pytest


def test_create_goal_forwards_duration(client, db_session, monkeypatch):
    captured = {}

    def fake(db, title, description, target_date, duration_value=None, duration_unit=None):
        captured.update(
            target_date=target_date,
            duration_value=duration_value,
            duration_unit=duration_unit,
        )
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    res = client.post(
        "/api/goals",
        json={"title": "目标", "duration_value": 3, "duration_unit": "month"},
    )
    assert res.status_code == 201
    assert captured == {
        "target_date": None,
        "duration_value": 3,
        "duration_unit": "month",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "目标", "duration_value": 0, "duration_unit": "day"},
        {"title": "目标", "duration_value": 3},
        {"title": "目标", "duration_unit": "week"},
        {"title": "目标", "duration_value": 1, "duration_unit": "year"},
        {
            "title": "目标",
            "target_date": "2099-01-01",
            "duration_value": 3,
            "duration_unit": "month",
        },
        {"title": "目标", "target_date": "2000-01-01"},
    ],
)
def test_create_goal_rejects_invalid_duration_contract(client, payload):
    assert client.post("/api/goals", json=payload).status_code == 422
```

- [ ] **Step 6: Run Goals API tests and verify RED**

Run:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_goals_api.py -v
```

Expected: duration-forwarding test fails because the request model drops the new fields; invalid combinations that currently pass reach the fake or LLM path instead of returning `422`.

- [ ] **Step 7: Implement the API request contract**

Change imports in `backend/app/api/goals.py`:

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator
```

Replace `GoalCreate` with:

```python
class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_date: date | None = None
    duration_value: int | None = Field(default=None, gt=0)
    duration_unit: Literal["day", "week", "month"] | None = None

    @model_validator(mode="after")
    def validate_schedule_input(self):
        if (self.duration_value is None) != (self.duration_unit is None):
            raise ValueError("duration_value 与 duration_unit 必须同时提供")
        if self.target_date is not None and self.duration_value is not None:
            raise ValueError("target_date 与预期完成时长不能同时提供")
        if self.target_date is not None and self.target_date < date.today():
            raise ValueError("target_date 不能早于今天")
        return self
```

Call the service with explicit keywords:

```python
goal = create_goal_with_plan(
    db,
    payload.title,
    payload.description,
    target_date=payload.target_date,
    duration_value=payload.duration_value,
    duration_unit=payload.duration_unit,
)
```

- [ ] **Step 8: Run focused and full backend verification, then commit**

Run:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_planner_service.py tests/test_goals_api.py -v
D:\conda\envs\dl2025\python.exe -m pytest
```

Expected: focused tests and the complete backend suite pass.

Commit:

```powershell
git add backend/app/services/planner_service.py backend/app/api/goals.py backend/tests/test_planner_service.py backend/tests/test_goals_api.py
git commit -m "feat: create goals from relative completion duration"
```

---

### Task 3: Duration Form and Typed Frontend Payload

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/GoalInput.tsx`
- Modify: `frontend/src/pages/DailyTasks.tsx`
- Modify: `frontend/src/index.css`
- Create: `frontend/src/pages/GoalInput.test.tsx`
- Create: `frontend/src/pages/DailyTasks.test.tsx`

**Interfaces:**
- Produces: `DurationUnit = 'day' | 'week' | 'month'`.
- Produces: `CreateGoalInput` with `title`, optional `description`, and required `duration_value`/`duration_unit` for the new UI.
- Preserves: `api.createGoal()` returning `Promise<GoalDTO>` and navigation to `/goals/:id`.
- Produces: completed task control with a 20px white filled circle and dark checkmark; incomplete state remains an outlined circle.

- [ ] **Step 1: Install the focused frontend test dependencies**

Run from `frontend/`:

```powershell
npm install --save-dev vitest@^2.1.0 jsdom@^25.0.0 @testing-library/react@^16.0.0 @testing-library/user-event@^14.0.0
```

Add the script to `frontend/package.json`:

```json
"test": "vitest run"
```

Add a `test` block to `frontend/vite.config.ts` and use Vitest's config type:

```typescript
/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
  },
})
```

- [ ] **Step 2: Write the failing form interaction test**

Create `frontend/src/pages/GoalInput.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { GoalInput } from './GoalInput'

vi.mock('../api/client', () => ({
  api: {
    listGoals: vi.fn(),
    createGoal: vi.fn(),
    deleteGoal: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

describe('GoalInput duration scheduling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.listGoals.mockResolvedValue([])
    mockedApi.createGoal.mockResolvedValue({
      id: 1,
      title: '学习 Python',
      description: '',
      target_date: '2026-11-13',
      created_at: '2026-08-13T00:00:00',
    })
  })

  it('submits a positive duration value and selected unit instead of a date', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><GoalInput /></MemoryRouter>)

    expect(screen.queryByLabelText('目标完成日期(可选)')).toBeNull()
    const duration = screen.getByLabelText('预期完成时间') as HTMLInputElement
    const unit = screen.getByLabelText('时间单位') as HTMLSelectElement
    expect(duration.value).toBe('30')
    expect(unit.value).toBe('day')

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    fireEvent.change(duration, { target: { value: '3' } })
    await user.selectOptions(unit, 'month')
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    await waitFor(() => {
      expect(mockedApi.createGoal).toHaveBeenCalledWith({
        title: '学习 Python',
        description: '',
        duration_value: 3,
        duration_unit: 'month',
      })
    })
  })

  it('does not submit a non-positive duration', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><GoalInput /></MemoryRouter>)

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    fireEvent.change(screen.getByLabelText('预期完成时间'), { target: { value: '0' } })
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    expect(await screen.findByText('预期完成时间必须是正整数')).toBeTruthy()
    expect(mockedApi.createGoal).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run the frontend test and verify RED**

Run:

```powershell
npm test -- src/pages/GoalInput.test.tsx
```

Expected: failure because the date label/input still exists and the duration controls do not.

- [ ] **Step 4: Add typed duration payloads to the API client**

In `frontend/src/api/client.ts`, add before `api`:

```typescript
export type DurationUnit = 'day' | 'week' | 'month'

export interface CreateGoalInput {
  title: string
  description?: string
  duration_value: number
  duration_unit: DurationUnit
}
```

Change `createGoal` to:

```typescript
createGoal: (body: CreateGoalInput) =>
  req<GoalDTO>('/goals', { method: 'POST', body: JSON.stringify(body) }),
```

- [ ] **Step 5: Replace the date input with accessible duration controls**

In `frontend/src/pages/GoalInput.tsx`, import the unit type:

```typescript
import type { DurationUnit } from '../api/client'
```

Replace `targetDate` state with:

```typescript
const [durationValue, setDurationValue] = useState('30')
const [durationUnit, setDurationUnit] = useState<DurationUnit>('day')
```

After the title trim guard in `onSubmit`, add:

```typescript
const parsedDuration = Number(durationValue)
if (!Number.isInteger(parsedDuration) || parsedDuration <= 0) {
  setError('预期完成时间必须是正整数')
  return
}
```

Change the create payload to:

```typescript
const goal = await api.createGoal({
  title: title.trim(),
  description: description.trim(),
  duration_value: parsedDuration,
  duration_unit: durationUnit,
})
```

Give the title input `id="goal-title"` and its label `htmlFor="goal-title"`. Replace the date label/input with:

```tsx
<label htmlFor="duration-value" className="dim" style={{ fontSize: 13, display: 'block', marginTop: 16 }}>
  预期完成时间
</label>
<div className="duration-row" style={{ marginTop: 6 }}>
  <input
    id="duration-value"
    type="number"
    className="input"
    min={1}
    step={1}
    required
    value={durationValue}
    onChange={(e) => setDurationValue(e.target.value)}
  />
  <label className="sr-only" htmlFor="duration-unit">时间单位</label>
  <select
    id="duration-unit"
    className="input"
    value={durationUnit}
    onChange={(e) => setDurationUnit(e.target.value as DurationUnit)}
  >
    <option value="day">天</option>
    <option value="week">周</option>
    <option value="month">月</option>
  </select>
</div>
<p className="faint" style={{ fontSize: 12, margin: '6px 0 0' }}>
  任务会从今天起（包含周末）均匀安排在这段时间内。
</p>
```

- [ ] **Step 6: Add compact responsive styling**

Append to `frontend/src/index.css` near the input section:

```css
.duration-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 110px;
  gap: 8px;
}

.duration-row select { color-scheme: dark; }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 420px) {
  .duration-row { grid-template-columns: minmax(0, 1fr) 88px; }
}
```

- [ ] **Step 7: Add a failing completion-toggle visual test**

Create `frontend/src/pages/DailyTasks.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import type { GoalDTO, TaskDTO } from '../types'
import { DailyTasks } from './DailyTasks'
import '../index.css'

vi.mock('../api/client', () => ({
  api: {
    getGoal: vi.fn(),
    setTaskCompleted: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)
const task: TaskDTO = {
  id: 7,
  title: '完成练习',
  description: '',
  type: 'practice',
  scheduled_date: new Date().toLocaleDateString('en-CA'),
  effort: 1,
  order: 0,
  status: 'todo',
  verified: false,
  completed_at: null,
}
const goal: GoalDTO = {
  id: 1,
  title: '测试目标',
  description: '',
  target_date: null,
  created_at: '2026-08-13T00:00:00',
  plan: {
    id: 1,
    strategy: '策略',
    status: 'active',
    milestones: [{
      id: 1,
      title: '阶段',
      description: '',
      order: 1,
      due_date: null,
      status: 'todo',
      tasks: [task],
    }],
  },
}

describe('DailyTasks completion control', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getGoal.mockResolvedValue(goal)
    mockedApi.setTaskCompleted.mockResolvedValue({
      ...task,
      status: 'done',
      completed_at: '2026-08-13T12:00:00',
    })
  })

  it('turns the outlined circle into a filled check control after completion', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/goals/1/daily']}>
        <Routes><Route path="/goals/:id/daily" element={<DailyTasks />} /></Routes>
      </MemoryRouter>,
    )

    const toggle = await screen.findByRole('button', { name: '标记完成' })
    expect(toggle.classList.contains('done')).toBe(false)
    expect(toggle.querySelector('svg')).toBeNull()

    await user.click(toggle)

    await waitFor(() => {
      const completed = screen.getByRole('button', { name: '标记未完成' })
      expect(completed.classList.contains('done')).toBe(true)
      expect(completed.querySelector('svg')).not.toBeNull()
      const style = getComputedStyle(completed)
      expect(style.width).toBe('20px')
      expect(style.height).toBe('20px')
      expect(style.backgroundColor).toBe('rgb(245, 245, 245)')
      expect(style.color).toBe('rgb(23, 23, 23)')
    })
    expect(mockedApi.setTaskCompleted).toHaveBeenCalledWith(7, true)
  })
})
```

Run:

```powershell
npm test -- src/pages/DailyTasks.test.tsx
```

Expected: the interaction behavior may already pass, but the visual contract is not yet exact because the current completed circle uses an 18px variable-driven style. Proceed to the CSS mutation check in Step 8 before implementation.

- [ ] **Step 8: Verify the visual test detects removal of the completed state, then implement the reference styling**

Temporarily remove `done` from the completed button class expression in `frontend/src/pages/DailyTasks.tsx`, run the Step 7 command, and confirm the test fails because the completed control lacks the `done` class. Restore the expression before continuing.

Keep the existing conditional `<IconCheck>` behavior, but change its size to:

```tsx
{t.status === 'done' && <IconCheck size={13} />}
```

Replace the `.circle-dot` and `.circle-dot.done` dimensional/color rules in `frontend/src/index.css` with:

```css
.circle-dot {
  width: 20px;
  height: 20px;
  padding: 0;
  border-radius: 50%;
  flex-shrink: 0;
  border: 2px solid var(--text-faint);
  background: transparent;
  color: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition), border-color var(--transition), transform var(--transition);
}

.circle-dot.done {
  background: #f5f5f5;
  border-color: #f5f5f5;
  color: #171717;
}
```

- [ ] **Step 9: Run the focused frontend tests and build**

Run:

```powershell
npm test -- src/pages/GoalInput.test.tsx src/pages/DailyTasks.test.tsx
npm run build
```

Expected: the interaction test passes and TypeScript/Vite build exits `0`.

- [ ] **Step 10: Commit the frontend feature**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/api/client.ts frontend/src/pages/GoalInput.tsx frontend/src/pages/GoalInput.test.tsx frontend/src/pages/DailyTasks.tsx frontend/src/pages/DailyTasks.test.tsx frontend/src/index.css
git commit -m "feat: collect expected completion duration"
```

---

### Task 4: End-to-End Verification and Documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: the duration input semantics, computed `target_date`, uniform natural-day scheduling, and legacy API compatibility.

- [ ] **Step 1: Update README behavior documentation**

Add this section after the introductory paragraph in `README.md`:

```markdown
## 排程规则

创建目标时输入正整数预期时长，并选择天、周或月。服务端以创建当天为开始日，计算并保存目标截止日期，再按任务顺序把计划均匀铺到整个自然日区间；周末也会安排任务。首个任务安排在当天，最后一个任务不晚于截止日。

`POST /api/goals` 使用 `duration_value` 与 `duration_unit`（`day` / `week` / `month`）。旧客户端仍可提交 `target_date`；未提供任何期限时保留按每日容量尽快安排的行为。
```

- [ ] **Step 2: Run fresh full verification**

Run from the repository root:

```powershell
Push-Location backend
D:\conda\envs\dl2025\python.exe -m pytest
Pop-Location
Push-Location frontend
npm test
npm run build
Pop-Location
git diff --check
```

Expected: all backend tests pass, all frontend tests pass, build exits `0`, and `git diff --check` prints no errors.

- [ ] **Step 3: Review the requirement checklist**

Verify each observable requirement against the implementation and tests:

```text
[ ] Form contains positive numeric duration and day/week/month selector
[ ] Form no longer contains native absolute-date input
[ ] Completed task control matches the white filled circle and dark checkmark reference
[ ] API rejects partial, invalid, or conflicting duration input with 422
[ ] Server persists the computed Goal.target_date
[ ] Day/week/calendar-month conversion is deterministic and month-end safe
[ ] Uniform schedule includes weekends and preserves task order
[ ] First/last task land on start/deadline for multi-task plans
[ ] Milestone due dates equal their final task date and never exceed target_date
[ ] Legacy target_date uniformly schedules; missing deadline keeps capacity mode
[ ] LLM code still does not assign dates
```

- [ ] **Step 4: Commit documentation**

```powershell
git add README.md
git commit -m "docs: explain duration-based scheduling"
```
