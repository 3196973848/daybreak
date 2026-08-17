import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import SessionLocal, get_db
from ..llm.tutor import LearningStage
from ..models import LearningSession, Task, User
from ..services.learning_service import (
    LearningGenerationError,
    LearningPersistenceError,
    LearningSessionNotFound,
    LearningTaskNotFound,
    LearningTaskTypeError,
    add_learning_turn,
    get_learning_session,
    goal_id_for,
    start_learning_session,
    stream_learning_turn_events,
)


router = APIRouter(prefix="/api/tasks", tags=["learning"])

TASK_NOT_FOUND = "学习任务不存在"
TASK_TYPE_ERROR = "该任务不支持学习会话"
SESSION_NOT_FOUND = "学习会话不存在"
GENERATION_ERROR = "导师回复生成失败，请稍后重试"
START_PERSISTENCE_ERROR = "导师会话保存失败，请稍后重试"
TURN_PERSISTENCE_ERROR = "导师回复保存失败，请稍后重试"


class LearningTurnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_turn_id: UUID
    message: str = Field(min_length=1, max_length=10000)
    model: str | None = None

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value


class LearningTurnResponse(BaseModel):
    id: int
    client_turn_id: str
    user_message: str | None
    assistant_message: str
    stage: LearningStage
    created_at: datetime


class LearningSessionResponse(BaseModel):
    id: int
    task_id: int
    goal_id: int
    task_title: str
    task_description: str
    stage: LearningStage
    covered_points: list[str]
    weak_points: list[str]
    ready_for_verification: bool
    estimated_hours_snapshot: float
    turns: list[LearningTurnResponse]


def _points(value: str) -> list[str]:
    try:
        points = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return points if isinstance(points, list) and all(isinstance(point, str) for point in points) else []


def _serialize(session: LearningSession) -> LearningSessionResponse:
    task = session.task
    return LearningSessionResponse(
        id=session.id,
        task_id=session.task_id,
        goal_id=goal_id_for(session),
        task_title=task.title,
        task_description=task.description,
        stage=session.stage,
        covered_points=_points(session.covered_points),
        weak_points=_points(session.weak_points),
        ready_for_verification=session.ready_for_verification,
        estimated_hours_snapshot=session.estimated_hours_snapshot,
        turns=[
            LearningTurnResponse(
                id=turn.id,
                client_turn_id=turn.client_turn_id,
                user_message=turn.user_message,
                assistant_message=turn.assistant_message,
                stage=turn.stage,
                created_at=turn.created_at,
            )
            for turn in session.turns
        ],
    )


def _raise_public_error(error: Exception, *, operation: str) -> None:
    if isinstance(error, LearningTaskNotFound):
        raise HTTPException(status_code=404, detail=TASK_NOT_FOUND) from None
    if isinstance(error, LearningTaskTypeError):
        raise HTTPException(status_code=422, detail=TASK_TYPE_ERROR) from None
    if isinstance(error, LearningSessionNotFound):
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from None
    if isinstance(error, LearningGenerationError):
        raise HTTPException(status_code=502, detail=GENERATION_ERROR) from None
    if isinstance(error, LearningPersistenceError):
        detail = START_PERSISTENCE_ERROR if operation == "start" else TURN_PERSISTENCE_ERROR
        raise HTTPException(status_code=502, detail=detail) from None
    raise error


def _owned_task(db: Session, task_id: int, user_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.milestone.plan.goal.user_id != user_id:
        raise HTTPException(status_code=404, detail=TASK_NOT_FOUND)
    return task


def _validate_model(model: str | None) -> None:
    if model is not None and model not in settings.available_models:
        raise HTTPException(status_code=422, detail="不支持的模型")


def _error_event(message: str) -> str:
    return f"event: error\ndata: {json.dumps({'message': message}, ensure_ascii=False)}\n\n"


@router.get("/{task_id}/learning-session", response_model=LearningSessionResponse)
def read_learning_session(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned_task(db, task_id, user.id)
    try:
        return _serialize(get_learning_session(db, task_id))
    except (
        LearningTaskNotFound,
        LearningTaskTypeError,
        LearningSessionNotFound,
        LearningGenerationError,
        LearningPersistenceError,
    ) as error:
        _raise_public_error(error, operation="read")


@router.post("/{task_id}/learning-session", response_model=LearningSessionResponse)
def begin_learning_session(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned_task(db, task_id, user.id)
    try:
        return _serialize(start_learning_session(db, task_id))
    except (
        LearningTaskNotFound,
        LearningTaskTypeError,
        LearningSessionNotFound,
        LearningGenerationError,
        LearningPersistenceError,
    ) as error:
        _raise_public_error(error, operation="start")


@router.post("/{task_id}/learning-session/turns", response_model=LearningSessionResponse)
def create_learning_turn(
    task_id: int,
    body: LearningTurnCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned_task(db, task_id, user.id)
    _validate_model(body.model)
    try:
        session, _ = add_learning_turn(
            db, task_id, str(body.client_turn_id), body.message, body.model
        )
        return _serialize(session)
    except (
        LearningTaskNotFound,
        LearningTaskTypeError,
        LearningSessionNotFound,
        LearningGenerationError,
        LearningPersistenceError,
    ) as error:
        _raise_public_error(error, operation="turn")


@router.post("/{task_id}/learning-session/turns/stream")
def stream_learning_turn(
    task_id: int,
    body: LearningTurnCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned_task(db, task_id, user.id)
    _validate_model(body.model)

    def generate():
        with SessionLocal() as stream_db:
            try:
                for kind, payload in stream_learning_turn_events(
                    stream_db,
                    task_id,
                    str(body.client_turn_id),
                    body.message,
                    body.model,
                ):
                    if kind == "reply":
                        yield (
                            "event: reply\n"
                            f"data: {json.dumps({'text': payload}, ensure_ascii=False)}\n\n"
                        )
                    else:
                        session, _ = payload
                        yield (
                            "event: done\n"
                            f"data: {_serialize(session).model_dump_json()}\n\n"
                        )
                        return
            except LearningTaskNotFound:
                yield _error_event(TASK_NOT_FOUND)
            except LearningTaskTypeError:
                yield _error_event(TASK_TYPE_ERROR)
            except LearningSessionNotFound:
                yield _error_event(SESSION_NOT_FOUND)
            except LearningGenerationError:
                yield _error_event(GENERATION_ERROR)
            except LearningPersistenceError:
                yield _error_event(TURN_PERSISTENCE_ERROR)
            except Exception:
                yield _error_event(TURN_PERSISTENCE_ERROR)

    return StreamingResponse(generate(), media_type="text/event-stream")
