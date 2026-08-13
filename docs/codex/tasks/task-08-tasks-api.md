# Task 8: Tasks API(勾选完成 + 检验流程)

## 目标

实现 Tasks REST 路由:勾选完成/取消(PATCH)、检验流程(GET 出题/交付要求 + POST 判分),含里程碑状态刷新;注册进 main.py;写 API 测试。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 8** 一节。

## 要创建/修改的文件

- Create `backend/app/api/tasks.py`
- Modify `backend/app/main.py`(注册 tasks router)
- Create `backend/tests/test_tasks_api.py`

## 路由(前端依赖,契约必须一致)

```
PATCH /api/tasks/{id}    body {completed: bool} → 200 serialize_task(更新后)
GET   /api/tasks/{id}/verification → 按 task.type 生成内容:
                                      learn → mode="test", content=generate_test(...)
                                      其他   → mode="deliver", content=generate_deliver_criteria(...)
                                      落一条草稿 VerificationRecord,返回 {mode, record_id, content}
POST  /api/tasks/{id}/verification  body {record_id, answers?, submission?} →
                                      判分,score>=0.7 通过(标记 verified+done+刷新里程碑),
                                      更新 record,返回 {passed, score, feedback, verified}
```

要点:
- `PASS_THRESHOLD = 0.7` 模块级常量;`passed = grade.score >= PASS_THRESHOLD` 在 API 层计算
- `_refresh_milestone(milestone)`:全部 done → "done";部分 → "active";否则 "todo"
- test 模式:用 `TestContent.model_validate_json(record.content)` 还原,`grade_test`;submission = str(answers)
- deliver 模式:取 `DeliverContent.model_validate_json(record.content).acceptance_criteria`,`grade_delivery`;submission = payload.submission
- 通过时:`task.verified = True; task.status = "done"; task.completed_at = task.completed_at or datetime.now()`
- record 更新:`record.submission`、`record.result = grade.model_dump_json()`、`record.passed = passed`
- 404(任务/记录不存在)、400(record 不属于该任务、缺少 answers/submission)

## 实现内容

### `backend/app/api/tasks.py`

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

### `backend/app/main.py`(修改)

在 `app.include_router(goals.router)` 后加 `app.include_router(tasks.router)`,并加导入 `from .api import tasks`。

### `backend/tests/test_tasks_api.py`

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

## 完成标准

1. 先写测试确认失败 → 再实现 → `cd backend && python -m pytest tests/test_tasks_api.py -v` → `4 passed`
2. 创建 git commit(`feat: tasks api with completion toggle and verification flow`)
3. 报告:提交 hash、测试摘要、concerns

## 提交命令

```bash
git add backend/app/api/tasks.py backend/app/main.py backend/tests/test_tasks_api.py
git commit -m "feat: tasks api with completion toggle and verification flow"
```

## 报告

- 提交 hash: `713aad7`
- pytest 摘要: `python -m pytest tests/test_tasks_api.py -v` → `4 passed, 2 warnings in 0.09s`
- concerns:
  - 当前受限沙箱禁止 pytest 写 SQLite/缓存，RED/GREEN 验证均在获批的沙箱外执行。
  - LLM 生成与评分由 monkeypatch fake 隔离；API 层的 `score >= 0.7`、记录更新、任务/里程碑状态更新由测试覆盖。
  - warnings 为第三方 `StarletteDeprecationWarning` 与 `TestContent` 类名触发的 `PytestCollectionWarning`。
