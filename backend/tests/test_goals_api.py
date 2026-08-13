from app.models import Goal, Milestone, Plan, Task


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

    def fake(db, title, description, target_date):
        return _build_goal(db_session)

    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    res = client.post("/api/goals", json={"title": "目标", "description": "说明"})
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "目标"
    assert body["plan"]["milestones"][0]["tasks"][0]["title"] == "任务1"


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
