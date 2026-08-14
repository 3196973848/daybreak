import pytest
from pydantic import ValidationError

from app.api.goals import GoalCreate
from app.models import Goal, Milestone, Plan, Task
from app.services.capacity import InsufficientCapacityError


def _build_goal(db_session):
    goal = Goal(title="目标", description="说明")
    db_session.add(goal)
    plan = Plan(goal_id=0, strategy="策略")
    goal.plan = plan
    ms = Milestone(title="里程碑1", order=1)
    plan.milestones.append(ms)
    ms.tasks.append(Task(title="任务1", type="learn", order=0, effort=1.0))
    db_session.commit()
    return goal


def test_create_goal(client, db_session, monkeypatch):
    from app.services.planner_service import create_goal_with_plan

    def fake(
        db,
        title,
        description,
        target_date,
        duration_value=None,
        duration_unit=None,
        daily_hours=2.0,
    ):
        assert daily_hours == 2.0
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    res = client.post("/api/goals", json={"title": "目标", "description": "说明"})
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "目标"
    assert body["plan"]["milestones"][0]["tasks"][0]["title"] == "任务1"


def test_create_goal_forwards_duration(client, db_session, monkeypatch):
    captured = {}

    def fake(
        db,
        title,
        description,
        target_date,
        duration_value=None,
        duration_unit=None,
        daily_hours=2.0,
    ):
        captured.update(
            target_date=target_date,
            duration_value=duration_value,
            duration_unit=duration_unit,
            daily_hours=daily_hours,
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
        "daily_hours": 2.0,
    }


def test_create_goal_forwards_valid_daily_hours(client, db_session, monkeypatch):
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    response = client.post(
        "/api/goals",
        json={"title": "目标", "daily_hours": 2.5},
    )

    assert response.status_code == 201
    assert captured["daily_hours"] == 2.5


@pytest.mark.parametrize("daily_hours", [True, "2", 0, -0.5, 0.75])
def test_create_goal_rejects_invalid_daily_hours_without_calling_service(
    client, monkeypatch, daily_hours
):
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    response = client.post(
        "/api/goals",
        json={
            "title": "目标",
            "duration_value": 7,
            "duration_unit": "day",
            "daily_hours": daily_hours,
        },
    )

    assert response.status_code == 422
    assert called is False


def test_goal_create_rejects_non_finite_daily_hours():
    with pytest.raises(ValidationError):
        GoalCreate(title="目标", daily_hours=float("inf"))


def test_create_goal_rejects_large_non_half_hour_value_without_calling_service(
    client, db_session, monkeypatch
):
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)

    response = client.post(
        "/api/goals",
        json={"title": "goal", "daily_hours": 1_000_000_000.25},
    )

    assert response.status_code == 422
    assert called is False


def test_create_goal_rejects_unrepresentable_integer_without_calling_service(
    client, db_session, monkeypatch
):
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)

    response = client.post(
        "/api/goals",
        json={"title": "goal", "daily_hours": 10**400},
    )

    assert response.status_code == 422
    assert called is False


def test_create_goal_forwards_large_representable_half_hour_value(
    client, db_session, monkeypatch
):
    captured = {}

    def fake(*args, **kwargs):
        captured.update(kwargs)
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)

    response = client.post(
        "/api/goals",
        json={"title": "goal", "daily_hours": 10**300},
    )

    assert response.status_code == 201
    assert captured["daily_hours"] == 1e300


def test_create_goal_returns_structured_capacity_error(client, monkeypatch):
    def fake(*args, **kwargs):
        raise InsufficientCapacityError(4.0, 4.0, 3)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    response = client.post(
        "/api/goals",
        json={
            "title": "目标",
            "duration_value": 2,
            "duration_unit": "day",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "insufficient_capacity",
        "message": "当前时间不足",
        "required_hours": 4.0,
        "available_hours": 4.0,
        "minimum_days": 3,
        "suggested_duration": {"value": 3, "unit": "day"},
    }


def test_create_goal_keeps_other_generation_errors_as_bad_gateway(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.goals.create_goal_with_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("模型离线")),
    )

    response = client.post("/api/goals", json={"title": "目标"})

    assert response.status_code == 502
    assert "模型离线" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "目标", "duration_value": 0, "duration_unit": "day"},
        {"title": "目标", "duration_value": True, "duration_unit": "day"},
        {"title": "目标", "duration_value": "3", "duration_unit": "day"},
        {"title": "目标", "duration_value": 1.0, "duration_unit": "day"},
        {"title": "目标", "duration_value": 1.5, "duration_unit": "day"},
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
def test_create_goal_rejects_invalid_duration_contract(
    client, db_session, monkeypatch, payload
):
    called = False

    def fake(*args, **kwargs):
        nonlocal called
        called = True
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    assert client.post("/api/goals", json=payload).status_code == 422
    assert called is False


def test_get_goal_not_found(client):
    res = client.get("/api/goals/999")
    assert res.status_code == 404


def test_delete_goal(client, db_session, monkeypatch):
    from app.services.planner_service import create_goal_with_plan

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", lambda *a, **k: _build_goal(db_session))
    created = client.post("/api/goals", json={"title": "目标"}).json()
    res = client.delete(f"/api/goals/{created['id']}")
    assert res.status_code == 200
    assert client.get(f"/api/goals/{created['id']}").status_code == 404


def test_list_goals(client, db_session, monkeypatch):
    from app.services.planner_service import create_goal_with_plan

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", lambda *a, **k: _build_goal(db_session))
    client.post("/api/goals", json={"title": "目标A"})
    client.post("/api/goals", json={"title": "目标B"})
    res = client.get("/api/goals")
    assert res.status_code == 200
    assert len(res.json()) == 2
