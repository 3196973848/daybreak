import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm.tutor import generate_tutor_turn
from ..models import LearningSession, LearningTurn, Task


class LearningTaskNotFound(Exception):
    pass


class LearningTaskTypeError(Exception):
    pass


class LearningSessionNotFound(Exception):
    pass


class LearningGenerationError(Exception):
    pass


class LearningPersistenceError(Exception):
    pass


def _learning_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise LearningTaskNotFound("Learning task was not found.")
    if task.type != "learn":
        raise LearningTaskTypeError("This task does not support learning sessions.")
    return task


def _session_for_task(db: Session, task: Task) -> LearningSession | None:
    return db.scalar(
        select(LearningSession).where(LearningSession.task_id == task.id)
    )


def _load_points(value: str) -> list[str]:
    try:
        points = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return points if isinstance(points, list) and all(isinstance(point, str) for point in points) else []


def _tutor_context(turns: list[LearningTurn]) -> list[dict[str, str | None]]:
    return [
        {
            "user_message": turn.user_message,
            "assistant_message": turn.assistant_message,
        }
        for turn in turns
    ]


def _generate(
    *,
    task: Task,
    estimated_hours: float,
    previous_summary: str,
    recent_turns: list[dict[str, str | None]],
    user_message: str | None,
    already_ready: bool,
):
    try:
        return generate_tutor_turn(
            task_title=task.title,
            task_description=task.description,
            estimated_hours=estimated_hours,
            previous_summary=previous_summary,
            recent_turns=recent_turns,
            user_message=user_message,
            already_ready=already_ready,
        )
    except RuntimeError:
        raise LearningGenerationError("Tutor response generation failed.") from None


def get_learning_session(db: Session, task_id: int) -> LearningSession:
    task = _learning_task(db, task_id)
    session = _session_for_task(db, task)
    if session is None:
        raise LearningSessionNotFound("Learning session was not found.")
    return session


def start_learning_session(db: Session, task_id: int) -> LearningSession:
    task = _learning_task(db, task_id)
    existing = _session_for_task(db, task)
    if existing is not None:
        return existing

    output = _generate(
        task=task,
        estimated_hours=task.effort,
        previous_summary="",
        recent_turns=[],
        user_message=None,
        already_ready=False,
    )
    session = LearningSession(
        task_id=task.id,
        stage=output.stage,
        session_summary=output.session_summary,
        covered_points=json.dumps(output.covered_points, ensure_ascii=False),
        weak_points=json.dumps(output.weak_points, ensure_ascii=False),
        ready_for_verification=output.ready_for_verification,
        estimated_hours_snapshot=task.effort,
        turns=[
            LearningTurn(
                client_turn_id="initial",
                user_message=None,
                assistant_message=output.reply,
                stage=output.stage,
            )
        ],
    )
    try:
        db.add(session)
        db.flush()
        db.refresh(session)
        db.commit()
    except Exception:
        db.rollback()
        raise LearningPersistenceError("Learning session could not be saved.") from None
    return session


def add_learning_turn(
    db: Session, task_id: int, client_turn_id: str, message: str
) -> tuple[LearningSession, LearningTurn]:
    task = _learning_task(db, task_id)
    session = _session_for_task(db, task)
    if session is None:
        raise LearningSessionNotFound("Learning session was not found.")

    existing = next(
        (turn for turn in session.turns if turn.client_turn_id == client_turn_id), None
    )
    if existing is not None:
        return session, existing

    if not isinstance(message, str) or not (message := message.strip()):
        raise ValueError("Learning message must not be blank.")

    output = _generate(
        task=task,
        estimated_hours=session.estimated_hours_snapshot,
        previous_summary=session.session_summary,
        recent_turns=_tutor_context(session.turns[-12:]),
        user_message=message,
        already_ready=session.ready_for_verification,
    )
    turn = LearningTurn(
        session_id=session.id,
        client_turn_id=client_turn_id,
        user_message=message,
        assistant_message=output.reply,
        stage=output.stage,
    )
    try:
        session.stage = output.stage
        session.session_summary = output.session_summary
        session.covered_points = json.dumps(output.covered_points, ensure_ascii=False)
        session.weak_points = json.dumps(output.weak_points, ensure_ascii=False)
        session.ready_for_verification = (
            session.ready_for_verification or output.ready_for_verification
        )
        db.add(turn)
        db.flush()
        db.refresh(session)
        db.commit()
    except Exception:
        db.rollback()
        raise LearningPersistenceError("Learning turn could not be saved.") from None
    return session, turn


def goal_id_for(session: LearningSession) -> int:
    return session.task.milestone.plan.goal_id
