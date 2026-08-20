import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..llm.verifier import (
    DeliverContent,
    TestContent,
    generate_deliver_criteria,
    generate_remedy_tasks,
    generate_test,
    grade_delivery,
    grade_short_answers,
    score_test,
)
from ..llm.schema import PlanSpec, MilestoneSpec, TaskSpec
from ..models import Milestone, Task, User, VerificationRecord
from ..scheduler.scheduler import schedule
from ..config import settings
from .goals import serialize_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

PASS_THRESHOLD = 0.7
VERIFICATION_GENERATION_ERROR = "检验生成失败，请稍后重试"
VERIFICATION_GRADING_ERROR = "检验评分失败，请稍后重试"
DELIVERY_GRADING_ERROR = "交付评分失败，请稍后重试"


class TaskComplete(BaseModel):
    completed: bool
    actual_minutes: float | None = None


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


def _historical_question_texts(content: str) -> list[str]:
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(value, dict) or not isinstance(value.get("questions"), list):
        return []
    texts = []
    for question in value["questions"]:
        if not isinstance(question, dict):
            continue
        text = question.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)
    return texts


def _owned_task(db: Session, task_id: int, user_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.milestone.plan.goal.user_id != user_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.patch("/{task_id}")
def set_complete(
    task_id: int,
    payload: TaskComplete,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _owned_task(db, task_id, user.id)
    if payload.completed:
        task.status = "done"
        task.completed_at = task.completed_at or datetime.now()
        if payload.actual_minutes is not None:
            task.actual_minutes = payload.actual_minutes
    else:
        task.status = "todo"
        task.completed_at = None
        task.actual_minutes = None
        task.verified = False
    _refresh_milestone(task.milestone)
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.get("/{task_id}/verification")
def start_verification(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _owned_task(db, task_id, user.id)
    try:
        if task.type == "learn":
            history = []
            for prior in task.verifications:
                if prior.mode == "test":
                    history.extend(_historical_question_texts(prior.content))
            content = generate_test(
                task.title, task.description, previous_question_texts=history
            )
            mode = "test"
            public_content = content.public_dump()
        else:
            content = generate_deliver_criteria(task.title, task.description)
            mode = "deliver"
            public_content = content.model_dump()
        record = VerificationRecord(
            task_id=task.id, mode=mode, content=content.model_dump_json(),
            submission="", result="", passed=False,
        )
        db.add(record)
        db.flush()
        db.refresh(record)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=502, detail=VERIFICATION_GENERATION_ERROR) from None
    return {"mode": mode, "record_id": record.id, "content": public_content}


@router.post("/{task_id}/verification")
def submit_verification(
    task_id: int,
    payload: VerificationSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _owned_task(db, task_id, user.id)
    record = db.get(VerificationRecord, payload.record_id)
    if not record or record.task_id != task.id:
        raise HTTPException(status_code=400, detail="检验记录不存在")

    if record.mode == "test":
        if payload.answers is None:
            raise HTTPException(status_code=400, detail="测试模式需提交 answers")
        try:
            content = TestContent.model_validate_json(record.content)
            short_grade = grade_short_answers(
                task.title, task.description, content, payload.answers
            )
            quiz_score = score_test(content, payload.answers, short_grade)
            grade_score = quiz_score.score
            record.result = quiz_score.model_dump_json()
            record.submission = json.dumps(payload.answers, ensure_ascii=False)
        except Exception:
            db.rollback()
            raise HTTPException(status_code=502, detail=VERIFICATION_GRADING_ERROR) from None
    else:
        if payload.submission is None:
            raise HTTPException(status_code=400, detail="交付模式需提交 submission")
        try:
            criteria = DeliverContent.model_validate_json(record.content).acceptance_criteria
            grade = grade_delivery(task.title, task.description, criteria, payload.submission)
            grade_score = grade.score
            record.result = grade.model_dump_json()
            record.submission = payload.submission
        except Exception:
            db.rollback()
            raise HTTPException(status_code=502, detail=DELIVERY_GRADING_ERROR) from None

    try:
        passed = grade_score >= PASS_THRESHOLD
        record.passed = passed
        if passed:
            task.verified = True
            task.status = "done"
            task.completed_at = task.completed_at or datetime.now()
            _refresh_milestone(task.milestone)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        if record.mode == "test":
            raise HTTPException(status_code=502, detail=VERIFICATION_GRADING_ERROR) from None
        raise HTTPException(status_code=502, detail=DELIVERY_GRADING_ERROR) from None
    response = {
        "passed": passed,
        "score": grade_score,
        "feedback": quiz_score.feedback if record.mode == "test" else grade.feedback,
        "verified": task.verified,
    }
    if record.mode == "test":
        response.update(points=quiz_score.points, details=quiz_score.details)

    # Generate remedy tasks on failure
    remedy_tasks = []
    if not passed:
        try:
            feedback_text = response["feedback"]
            remedy = generate_remedy_tasks(task.title, task.description, feedback_text)
            today = date.today()
            for rt in remedy.tasks:
                spec = PlanSpec(strategy="remedy", milestones=[
                    MilestoneSpec(title="补强", order=0, tasks=[
                        TaskSpec(title=rt.title, description=rt.description, type=rt.type, effort_hours=rt.effort_hours)
                    ])
                ])
                scheduled = schedule(spec, today, blocks_per_day=settings.blocks_per_day, hours_per_block=settings.hours_per_block)
                new_task = Task(
                    milestone_id=task.milestone_id, title=rt.title, description=rt.description,
                    type=rt.type, effort=rt.effort_hours, order=len(task.milestone.tasks),
                    scheduled_date=scheduled[0].date if scheduled else today,
                    status="todo", verified=False,
                )
                db.add(new_task)
                remedy_tasks.append({"title": rt.title, "scheduled_date": new_task.scheduled_date.isoformat()})
            db.commit()
        except Exception:
            pass  # Don't fail verification if remedy generation fails

    if remedy_tasks:
        response["remedy_tasks"] = remedy_tasks
    return response
