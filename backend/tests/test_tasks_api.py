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
