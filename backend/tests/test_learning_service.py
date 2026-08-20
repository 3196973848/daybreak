import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.llm.tutor import TutorOutput
from app.models import Goal, LearningSession, LearningTurn, Milestone, Plan, Task
from app.services.learning_service import (
    LearningGenerationError,
    LearningPersistenceError,
    LearningSessionNotFound,
    LearningTaskNotFound,
    LearningTaskTypeError,
    add_learning_turn,
    get_learning_session,
    goal_id_for,
    start_learning_session,
)


def _task(db_session, *, task_type="learn", effort=2.5):
    goal = Goal(title="Learn Python", description="Build a solid foundation")
    plan = Plan(strategy="Daily practice")
    milestone = Milestone(title="Basics", order=1)
    task = Task(
        title="Functions",
        description="Understand function arguments and returns",
        type=task_type,
        effort=effort,
        order=0,
    )
    goal.plan = plan
    plan.milestones.append(milestone)
    milestone.tasks.append(task)
    db_session.add(goal)
    db_session.commit()
    return task


def _tutor_output(stage="diagnose", ready=False, **overrides):
    values = {
        "reply": "Start by explaining what a function returns.",
        "stage": stage,
        "session_summary": "The learner is working on function basics.",
        "covered_points": ["function definition"],
        "weak_points": ["return values"],
        "ready_for_verification": ready,
    }
    values.update(overrides)
    return TutorOutput.model_validate(values)


def _patch_tutor(monkeypatch, outputs):
    calls = []
    queue = list(outputs)

    def fake_tutor(**kwargs):
        calls.append(kwargs)
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("app.services.learning_service.generate_tutor_turn", fake_tutor)
    return calls


def _concurrent_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'learning-concurrency.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with session_factory() as setup_session:
        task_id = _task(setup_session).id
    return engine, session_factory, task_id


def _patch_concurrent_tutor(monkeypatch, output):
    calls = []
    calls_lock = Lock()
    second_call = Event()

    def fake_tutor(**kwargs):
        with calls_lock:
            calls.append(kwargs)
            call_number = len(calls)
            if call_number == 2:
                second_call.set()
        if call_number == 1:
            second_call.wait(timeout=1)
        return output

    monkeypatch.setattr("app.services.learning_service.generate_tutor_turn", fake_tutor)
    return calls


def test_start_creates_a_diagnostic_session_with_an_initial_turn_and_effort_snapshot(
    db_session, monkeypatch
):
    task = _task(db_session, effort=3.25)
    calls = _patch_tutor(monkeypatch, [_tutor_output()])

    session = start_learning_session(db_session, task.id)

    assert len(calls) == 1
    assert session.task_id == task.id
    assert session.estimated_hours_snapshot == 3.25
    assert session.stage == "diagnose"
    assert json.loads(session.covered_points) == ["function definition"]
    assert json.loads(session.weak_points) == ["return values"]
    assert len(session.turns) == 1
    assert session.turns[0].client_turn_id == "initial"
    assert session.turns[0].user_message is None
    assert session.turns[0].assistant_message == "Start by explaining what a function returns."


def test_start_is_idempotent_and_does_not_generate_a_second_diagnostic(db_session, monkeypatch):
    task = _task(db_session)
    calls = _patch_tutor(monkeypatch, [_tutor_output()])

    first = start_learning_session(db_session, task.id)
    second = start_learning_session(db_session, task.id)

    assert second.id == first.id
    assert len(calls) == 1
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 1


def test_simultaneous_start_returns_one_saved_session_with_one_model_call(
    tmp_path, monkeypatch
):
    engine, session_factory, task_id = _concurrent_database(tmp_path)
    calls = _patch_concurrent_tutor(monkeypatch, _tutor_output())
    start_barrier = Barrier(3)

    def worker():
        with session_factory() as worker_session:
            start_barrier.wait()
            session = start_learning_session(worker_session, task_id)
            return session.id

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            start_barrier.wait()
            session_ids = [future.result(timeout=5) for future in futures]

        with session_factory() as check_session:
            saved_count = check_session.scalar(
                select(func.count()).select_from(LearningSession)
            )
        assert session_ids[0] == session_ids[1]
        assert len(calls) == 1
        assert saved_count == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("task_id", "task_type", "error"),
    [
        (999, None, LearningTaskNotFound),
        (None, "practice", LearningTaskTypeError),
    ],
)
def test_start_rejects_missing_or_non_learning_tasks_before_model_invocation(
    db_session, monkeypatch, task_id, task_type, error
):
    task = _task(db_session, task_type=task_type) if task_type else None
    calls = _patch_tutor(monkeypatch, [_tutor_output()])

    with pytest.raises(error):
        start_learning_session(db_session, task.id if task else task_id)

    assert calls == []


def test_get_learning_session_distinguishes_missing_session_after_task_validation(db_session):
    learn_task = _task(db_session)
    practice_task = _task(db_session, task_type="practice")

    with pytest.raises(LearningSessionNotFound):
        get_learning_session(db_session, learn_task.id)
    with pytest.raises(LearningTaskTypeError):
        get_learning_session(db_session, practice_task.id)
    with pytest.raises(LearningTaskNotFound):
        get_learning_session(db_session, 999)


def test_goal_id_for_returns_the_session_tasks_goal_id(db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output()])

    session = start_learning_session(db_session, task.id)

    assert goal_id_for(session) == task.milestone.plan.goal_id


@pytest.mark.parametrize("method_name", ["get", "scalar"])
def test_database_read_failure_is_safely_mapped_and_session_remains_reusable(
    db_session, monkeypatch, method_name
):
    task = _task(db_session)
    calls = _patch_tutor(monkeypatch, [_tutor_output()])
    original = getattr(db_session, method_name)

    def fail(*args, **kwargs):
        raise RuntimeError("private database read detail")

    monkeypatch.setattr(db_session, method_name, fail)
    with pytest.raises(LearningPersistenceError) as error:
        start_learning_session(db_session, task.id)

    assert "private database read detail" not in str(error.value)
    monkeypatch.setattr(db_session, method_name, original)
    recovered = start_learning_session(db_session, task.id)
    assert recovered.task_id == task.id
    assert len(calls) == 1


def test_turn_lazy_load_failure_is_safely_mapped_and_retry_succeeds(
    db_session, monkeypatch
):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output()])
    session = start_learning_session(db_session, task.id)
    calls = _patch_tutor(monkeypatch, [_tutor_output(stage="explain")])
    db_session.expire(session, ["turns"])

    def fail_turn_read(conn, cursor, statement, parameters, context, executemany):
        if "FROM learning_turns" in statement:
            raise RuntimeError("private lazy-load detail")

    event.listen(db_session.bind, "before_cursor_execute", fail_turn_read)
    try:
        with pytest.raises(LearningPersistenceError) as error:
            add_learning_turn(db_session, task.id, "retry-lazy-read", "Continue")
    finally:
        event.remove(db_session.bind, "before_cursor_execute", fail_turn_read)

    assert "private lazy-load detail" not in str(error.value)
    _, recovered = add_learning_turn(
        db_session, task.id, "retry-lazy-read", "Continue"
    )
    assert recovered.client_turn_id == "retry-lazy-read"
    assert len(calls) == 1


def test_goal_traversal_failure_is_safely_mapped_and_retry_succeeds(
    db_session, monkeypatch
):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output()])
    session = start_learning_session(db_session, task.id)
    expected_goal_id = task.milestone.plan.goal_id
    db_session.expire_all()

    def fail_task_read(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT"):
            raise RuntimeError("private goal traversal detail")

    event.listen(db_session.bind, "before_cursor_execute", fail_task_read)
    try:
        with pytest.raises(LearningPersistenceError) as error:
            goal_id_for(session)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", fail_task_read)

    assert "private goal traversal detail" not in str(error.value)
    assert goal_id_for(session) == expected_goal_id


def test_turn_sends_summary_and_the_latest_twelve_persisted_turns(db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output()])
    session = start_learning_session(db_session, task.id)
    session.session_summary = "Existing summary"
    for index in range(13):
        session.turns.append(
            LearningTurn(
                client_turn_id=f"existing-{index}",
                user_message=f"question {index}",
                assistant_message=f"answer {index}",
                stage="explain",
            )
        )
    db_session.commit()
    calls = _patch_tutor(monkeypatch, [_tutor_output(stage="practice")])

    add_learning_turn(db_session, task.id, "next", " Please continue ")

    assert len(calls) == 1
    request = calls[0]
    assert request["previous_summary"] == "Existing summary"
    assert request["user_message"] == "Please continue"
    assert [turn["assistant_message"] for turn in request["recent_turns"]] == [
        f"answer {index}" for index in range(1, 13)
    ]
    assert [turn["user_message"] for turn in request["recent_turns"]] == [
        f"question {index}" for index in range(1, 13)
    ]


def test_turn_replaces_learning_state_and_stores_stage_transition(db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output(stage="practice")])
    session = start_learning_session(db_session, task.id)
    calls = _patch_tutor(
        monkeypatch,
        [
            _tutor_output(
                stage="remediate",
                covered_points=["parameters"],
                weak_points=["default values"],
                session_summary="Practice showed a gap in defaults.",
            )
        ],
    )

    saved_session, turn = add_learning_turn(db_session, task.id, "practice-1", "My answer")

    assert len(calls) == 1
    assert saved_session.id == session.id
    assert turn.stage == "remediate"
    assert saved_session.stage == "remediate"
    assert saved_session.session_summary == "Practice showed a gap in defaults."
    assert json.loads(saved_session.covered_points) == ["parameters"]
    assert json.loads(saved_session.weak_points) == ["default values"]


def test_turn_keeps_verification_readiness_after_later_remediation(db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output(stage="ready", ready=True)])
    session = start_learning_session(db_session, task.id)
    calls = _patch_tutor(monkeypatch, [_tutor_output(stage="remediate", ready=False)])

    saved_session, _ = add_learning_turn(db_session, task.id, "follow-up", "Can we revisit this?")

    assert len(calls) == 1
    assert saved_session.stage == "remediate"
    assert saved_session.ready_for_verification is True


def test_turn_returns_saved_turn_for_a_repeated_client_turn_id_without_regenerating(
    db_session, monkeypatch
):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output()])
    session = start_learning_session(db_session, task.id)
    calls = _patch_tutor(monkeypatch, [_tutor_output(stage="explain")])

    _, first = add_learning_turn(db_session, task.id, "same-turn", "First version")
    returned_session, second = add_learning_turn(db_session, task.id, "same-turn", "Ignored retry")

    assert returned_session.id == session.id
    assert second.id == first.id
    assert second.user_message == "First version"
    assert len(calls) == 1
    assert db_session.scalar(
        select(func.count()).select_from(LearningTurn).where(
            LearningTurn.session_id == session.id,
            LearningTurn.client_turn_id == "same-turn",
        )
    ) == 1


def test_simultaneous_same_client_turn_returns_one_saved_turn_with_one_model_call(
    tmp_path, monkeypatch
):
    engine, session_factory, task_id = _concurrent_database(tmp_path)
    _patch_tutor(monkeypatch, [_tutor_output()])
    with session_factory() as setup_session:
        learning_session_id = start_learning_session(setup_session, task_id).id

    calls = _patch_concurrent_tutor(monkeypatch, _tutor_output(stage="explain"))
    start_barrier = Barrier(3)

    def worker():
        with session_factory() as worker_session:
            start_barrier.wait()
            _, turn = add_learning_turn(
                worker_session, task_id, "concurrent-turn", "Continue"
            )
            return turn.id, turn.user_message

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            start_barrier.wait()
            returned = [future.result(timeout=5) for future in futures]

        with session_factory() as check_session:
            saved_count = check_session.scalar(
                select(func.count()).select_from(LearningTurn).where(
                    LearningTurn.session_id == learning_session_id,
                    LearningTurn.client_turn_id == "concurrent-turn",
                )
            )
        assert returned[0] == returned[1]
        assert returned[0][1] == "Continue"
        assert len(calls) == 1
        assert saved_count == 1
    finally:
        engine.dispose()


def test_start_model_failure_does_not_create_an_empty_session(db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [RuntimeError("untrusted adapter detail")])

    with pytest.raises(LearningGenerationError) as error:
        start_learning_session(db_session, task.id)

    assert "untrusted adapter detail" not in str(error.value)
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningTurn)) == 0


def test_turn_model_failure_does_not_mutate_an_existing_session(db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output(stage="practice")])
    session = start_learning_session(db_session, task.id)
    original = {
        "stage": session.stage,
        "summary": session.session_summary,
        "covered": session.covered_points,
        "weak": session.weak_points,
        "ready": session.ready_for_verification,
        "turn_count": len(session.turns),
    }
    _patch_tutor(monkeypatch, [RuntimeError("untrusted adapter detail")])

    with pytest.raises(LearningGenerationError) as error:
        add_learning_turn(db_session, task.id, "failed-model", "Try this")

    db_session.expire_all()
    unchanged = db_session.get(LearningSession, session.id)
    assert "untrusted adapter detail" not in str(error.value)
    assert unchanged.stage == original["stage"]
    assert unchanged.session_summary == original["summary"]
    assert unchanged.covered_points == original["covered"]
    assert unchanged.weak_points == original["weak"]
    assert unchanged.ready_for_verification == original["ready"]
    assert len(unchanged.turns) == original["turn_count"]


@pytest.mark.parametrize("method_name", ["flush", "refresh", "commit"])
def test_start_persistence_failure_rolls_back_without_creating_a_session(
    db_session, monkeypatch, method_name
):
    task = _task(db_session)
    calls = _patch_tutor(monkeypatch, [_tutor_output(), _tutor_output()])
    original = getattr(db_session, method_name)

    def fail(*args, **kwargs):
        raise RuntimeError("database internals")

    monkeypatch.setattr(db_session, method_name, fail)
    with pytest.raises(LearningPersistenceError) as error:
        start_learning_session(db_session, task.id)

    assert "database internals" not in str(error.value)
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 0
    monkeypatch.setattr(db_session, method_name, original)
    started = start_learning_session(db_session, task.id)
    assert started.id is not None
    assert len(calls) == 2


@pytest.mark.parametrize("method_name", ["flush", "refresh", "commit"])
def test_turn_persistence_failure_rolls_back_and_session_remains_reusable(
    db_session, monkeypatch, method_name
):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_tutor_output(stage="practice")])
    session = start_learning_session(db_session, task.id)
    original_state = (
        session.stage,
        session.session_summary,
        session.covered_points,
        session.weak_points,
        session.ready_for_verification,
        len(session.turns),
    )
    calls = _patch_tutor(
        monkeypatch,
        [_tutor_output(stage="remediate"), _tutor_output(stage="remediate")],
    )
    original = getattr(db_session, method_name)

    def fail(*args, **kwargs):
        raise RuntimeError("database internals")

    monkeypatch.setattr(db_session, method_name, fail)
    with pytest.raises(LearningPersistenceError) as error:
        add_learning_turn(db_session, task.id, "retryable", "Needs retry")

    assert "database internals" not in str(error.value)
    db_session.expire_all()
    unchanged = db_session.get(LearningSession, session.id)
    assert (
        unchanged.stage,
        unchanged.session_summary,
        unchanged.covered_points,
        unchanged.weak_points,
        unchanged.ready_for_verification,
        len(unchanged.turns),
    ) == original_state
    assert db_session.scalar(
        select(func.count()).select_from(LearningTurn).where(
            LearningTurn.session_id == session.id,
            LearningTurn.client_turn_id == "retryable",
        )
    ) == 0

    monkeypatch.setattr(db_session, method_name, original)
    _, retry = add_learning_turn(db_session, task.id, "retryable", "Needs retry")
    assert retry.id is not None
    assert len(calls) == 2
