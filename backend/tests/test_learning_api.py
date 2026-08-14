from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.llm.tutor import TutorOutput
from app.models import Goal, LearningSession, LearningTurn, Milestone, Plan, Task


MODEL_ERROR = "导师回复生成失败，请稍后重试"
START_PERSISTENCE_ERROR = "导师会话保存失败，请稍后重试"
TURN_PERSISTENCE_ERROR = "导师回复保存失败，请稍后重试"


def _task(db_session, *, task_type="learn", effort=3.5):
    goal = Goal(title="Learn Python", description="A goal description")
    plan = Plan(strategy="Practice daily")
    milestone = Milestone(title="Functions", order=1)
    task = Task(
        title="Function returns",
        description="Understand return values",
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


def _output(stage="diagnose", ready=False, **overrides):
    values = {
        "reply": "Explain what a function returns.",
        "stage": stage,
        "session_summary": "PRIVATE_SESSION_SUMMARY",
        "covered_points": ["return values"],
        "weak_points": ["parameters"],
        "ready_for_verification": ready,
    }
    values.update(overrides)
    return TutorOutput.model_validate(values)


def _patch_tutor(monkeypatch, outputs):
    calls = []
    queued = list(outputs)

    def tutor(**kwargs):
        calls.append(kwargs)
        result = queued.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("app.services.learning_service.generate_tutor_turn", tutor)
    return calls


def _start(client, task_id):
    return client.post(f"/api/tasks/{task_id}/learning-session")


def test_get_returns_full_ordered_history_and_goal_navigation(client, db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_output()])
    started = _start(client, task.id)
    assert started.status_code == 200
    session = db_session.scalar(select(LearningSession).where(LearningSession.task_id == task.id))
    session.turns.extend(
        [
            LearningTurn(
                client_turn_id="second", user_message="Question 1", assistant_message="Answer 1", stage="explain"
            ),
            LearningTurn(
                client_turn_id="third", user_message="Question 2", assistant_message="Answer 2", stage="practice"
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/tasks/{task.id}/learning-session")

    assert response.status_code == 200
    assert response.json() == {
        "id": session.id,
        "task_id": task.id,
        "goal_id": task.milestone.plan.goal_id,
        "task_title": "Function returns",
        "task_description": "Understand return values",
        "stage": "diagnose",
        "covered_points": ["return values"],
        "weak_points": ["parameters"],
        "ready_for_verification": False,
        "estimated_hours_snapshot": 3.5,
        "turns": [
            {
                "id": session.turns[0].id,
                "client_turn_id": "initial",
                "user_message": None,
                "assistant_message": "Explain what a function returns.",
                "stage": "diagnose",
                "created_at": session.turns[0].created_at.isoformat(),
            },
            {
                "id": session.turns[1].id,
                "client_turn_id": "second",
                "user_message": "Question 1",
                "assistant_message": "Answer 1",
                "stage": "explain",
                "created_at": session.turns[1].created_at.isoformat(),
            },
            {
                "id": session.turns[2].id,
                "client_turn_id": "third",
                "user_message": "Question 2",
                "assistant_message": "Answer 2",
                "stage": "practice",
                "created_at": session.turns[2].created_at.isoformat(),
            },
        ],
    }


@pytest.mark.parametrize("task_id", [999])
def test_get_returns_404_for_missing_task_or_session(client, db_session, task_id):
    response = client.get(f"/api/tasks/{task_id}/learning-session")
    assert response.status_code == 404

    task = _task(db_session)
    response = client.get(f"/api/tasks/{task.id}/learning-session")
    assert response.status_code == 404


def test_get_rejects_non_learning_tasks(client, db_session):
    task = _task(db_session, task_type="practice")
    response = client.get(f"/api/tasks/{task.id}/learning-session")
    assert response.status_code == 422


def test_start_creates_then_idempotently_resumes_a_sanitized_session(client, db_session, monkeypatch):
    task = _task(db_session)
    calls = _patch_tutor(monkeypatch, [_output()])

    first = _start(client, task.id)
    second = _start(client, task.id)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1
    text = first.text
    for secret in ("session_summary", "PRIVATE_SESSION_SUMMARY", "PRIVATE_RAW_MODEL_JSON", "private internal exception text"):
        assert secret not in text
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 1


def test_start_maps_model_failure_to_a_stable_sanitized_response(client, db_session, monkeypatch):
    task = _task(db_session)
    sentinel = "PRIVATE_RAW_MODEL_JSON and private internal exception text"
    _patch_tutor(monkeypatch, [RuntimeError(sentinel)])

    response = _start(client, task.id)

    assert response.status_code == 502
    assert response.json() == {"detail": MODEL_ERROR}
    assert sentinel not in response.text
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningTurn)) == 0


def test_start_maps_persistence_failure_without_partial_rows_and_can_retry(client, db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_output(), _output()])
    original_commit = db_session.commit
    sentinel = "PRIVATE_DATABASE_PARAMETERS"

    def fail_commit():
        raise RuntimeError(sentinel)

    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = _start(client, task.id)

    assert response.status_code == 502
    assert response.json() == {"detail": START_PERSISTENCE_ERROR}
    assert sentinel not in response.text
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningTurn)) == 0

    monkeypatch.setattr(db_session, "commit", original_commit)
    recovered = _start(client, task.id)
    assert recovered.status_code == 200
    assert db_session.scalar(select(func.count()).select_from(LearningSession)) == 1


def test_create_turn_returns_trimmed_message_and_idempotently_retries(client, db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_output(), _output(stage="explain")])
    assert _start(client, task.id).status_code == 200
    client_turn_id = str(uuid4())

    first = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": client_turn_id, "message": "  What is returned?  "},
    )
    retry = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": client_turn_id, "message": "Ignored duplicate"},
    )

    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()
    assert first.json()["turns"][-1]["user_message"] == "What is returned?"
    assert len(first.json()["turns"]) == 2


def test_create_turn_returns_404_without_a_session(client, db_session):
    task = _task(db_session)
    response = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": str(uuid4()), "message": "Continue"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"client_turn_id": str(uuid4()), "message": "   "},
        {"client_turn_id": str(uuid4()), "message": "Continue", "extra": True},
        {"client_turn_id": "not-a-uuid", "message": "Continue"},
    ],
)
def test_create_turn_rejects_invalid_payloads(client, db_session, payload):
    task = _task(db_session)
    response = client.post(f"/api/tasks/{task.id}/learning-session/turns", json=payload)
    assert response.status_code == 422


def test_create_turn_rejects_non_learning_tasks(client, db_session):
    task = _task(db_session, task_type="project")
    response = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": str(uuid4()), "message": "Continue"},
    )
    assert response.status_code == 422


def test_create_turn_maps_model_failure_to_a_stable_sanitized_response(client, db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_output(), RuntimeError("PRIVATE_RAW_MODEL_JSON")])
    assert _start(client, task.id).status_code == 200

    response = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": str(uuid4()), "message": "Continue"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": MODEL_ERROR}
    assert "PRIVATE_RAW_MODEL_JSON" not in response.text


def test_create_turn_maps_persistence_failure_without_partial_rows_and_can_retry(client, db_session, monkeypatch):
    task = _task(db_session)
    _patch_tutor(monkeypatch, [_output(), _output(stage="explain"), _output(stage="explain")])
    started = _start(client, task.id)
    assert started.status_code == 200
    session_id = started.json()["id"]
    client_turn_id = str(uuid4())
    original_commit = db_session.commit
    sentinel = "PRIVATE_DATABASE_PARAMETERS"

    def fail_commit():
        raise RuntimeError(sentinel)

    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": client_turn_id, "message": "Continue"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": TURN_PERSISTENCE_ERROR}
    assert sentinel not in response.text
    assert db_session.scalar(
        select(func.count()).select_from(LearningTurn).where(
            LearningTurn.session_id == session_id,
            LearningTurn.client_turn_id == client_turn_id,
        )
    ) == 0

    monkeypatch.setattr(db_session, "commit", original_commit)
    recovered = client.post(
        f"/api/tasks/{task.id}/learning-session/turns",
        json={"client_turn_id": client_turn_id, "message": "Continue"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["turns"][-1]["client_turn_id"] == client_turn_id
