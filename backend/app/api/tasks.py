import json
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
    grade_short_answers,
    score_test,
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
        # 取消完成即撤销已验证状态,保持状态一致
        task.verified = False
    _refresh_milestone(task.milestone)
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.get("/{task_id}/verification")
def start_verification(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        if task.type == "learn":
            history = []
            for prior in task.verifications:
                if prior.mode == "test":
                    prior_content = TestContent.model_validate_json(prior.content)
                    history.extend(question.text for question in prior_content.questions)
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
        db.commit()
        db.refresh(record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"检验题生成失败：{exc}") from exc
    return {"mode": mode, "record_id": record.id, "content": public_content}


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
        try:
            content = TestContent.model_validate_json(record.content)
            short_grade = grade_short_answers(
                task.title, task.description, content, payload.answers
            )
            quiz_score = score_test(content, payload.answers, short_grade)
            grade_score = quiz_score.score
            record.result = quiz_score.model_dump_json()
            record.submission = json.dumps(payload.answers, ensure_ascii=False)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"检验题评分失败：{exc}") from exc
    else:
        if payload.submission is None:
            raise HTTPException(status_code=400, detail="交付模式需提交 submission")
        try:
            criteria = DeliverContent.model_validate_json(record.content).acceptance_criteria
            grade = grade_delivery(task.title, task.description, criteria, payload.submission)
            grade_score = grade.score
            record.result = grade.model_dump_json()
            record.submission = payload.submission
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"交付评分失败：{exc}") from exc

    passed = grade_score >= PASS_THRESHOLD
    record.passed = passed
    if passed:
        task.verified = True
        task.status = "done"
        task.completed_at = task.completed_at or datetime.now()
        _refresh_milestone(task.milestone)
    db.commit()
    response = {
        "passed": passed,
        "score": grade_score,
        "feedback": quiz_score.feedback if record.mode == "test" else grade.feedback,
        "verified": task.verified,
    }
    if record.mode == "test":
        response.update(points=quiz_score.points, details=quiz_score.details)
    return response
