import json
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from ..llm.tutor import generate_tutor_turn
from ..models import LearningSession, LearningTurn, Task


_TASK_LOCK_STRIPES = tuple(Lock() for _ in range(64))


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


def _raise_read_error(db: Session | None) -> None:
    if db is not None:
        try:
            db.rollback()
        except Exception:
            pass
    raise LearningPersistenceError("Learning data could not be read.") from None


def _learning_task(db: Session, task_id: int) -> Task:
    try:
        task = db.get(Task, task_id)
        task_type = task.type if task is not None else None
    except Exception:
        _raise_read_error(db)
    if task is None:
        raise LearningTaskNotFound("Learning task was not found.")
    if task_type != "learn":
        raise LearningTaskTypeError("This task does not support learning sessions.")
    return task


def _session_for_task(db: Session, task: Task) -> LearningSession | None:
    try:
        return db.scalar(
            select(LearningSession).where(LearningSession.task_id == task.id)
        )
    except Exception:
        _raise_read_error(db)


def _session_turns(db: Session, session: LearningSession) -> list[LearningTurn]:
    try:
        return list(session.turns)
    except Exception:
        _raise_read_error(db)


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


def _task_lock(task_id: int) -> Lock:
    return _TASK_LOCK_STRIPES[task_id % len(_TASK_LOCK_STRIPES)]


def _start_learning_session(db: Session, task_id: int) -> LearningSession:
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


def start_learning_session(db: Session, task_id: int) -> LearningSession:
    with _task_lock(task_id):
        return _start_learning_session(db, task_id)


def _add_learning_turn(
    db: Session, task_id: int, client_turn_id: str, message: str
) -> tuple[LearningSession, LearningTurn]:
    task = _learning_task(db, task_id)
    session = _session_for_task(db, task)
    if session is None:
        raise LearningSessionNotFound("Learning session was not found.")

    turns = _session_turns(db, session)
    existing = next(
        (turn for turn in turns if turn.client_turn_id == client_turn_id), None
    )
    if existing is not None:
        return session, existing

    if not isinstance(message, str) or not (message := message.strip()):
        raise ValueError("Learning message must not be blank.")

    try:
        estimated_hours = session.estimated_hours_snapshot
        previous_summary = session.session_summary
        recent_turns = _tutor_context(turns[-12:])
        already_ready = session.ready_for_verification
    except Exception:
        _raise_read_error(db)
    output = _generate(
        task=task,
        estimated_hours=estimated_hours,
        previous_summary=previous_summary,
        recent_turns=recent_turns,
        user_message=message,
        already_ready=already_ready,
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


def add_learning_turn(
    db: Session, task_id: int, client_turn_id: str, message: str
) -> tuple[LearningSession, LearningTurn]:
    with _task_lock(task_id):
        return _add_learning_turn(db, task_id, client_turn_id, message)


def goal_id_for(session: LearningSession) -> int:
    db = object_session(session)
    try:
        return session.task.milestone.plan.goal_id
    except Exception:
        _raise_read_error(db)
