import json

from app.llm.verifier import DeliverContent, GradeResult, ShortGradeResult, TestContent
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


def _quiz_content():
    questions = [
        {
            "id": i,
            "type": "choice",
            "text": f"Q{i}",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "reference_answer": None,
            "rubric_points": [],
        }
        for i in range(1, 8)
    ]
    questions.extend(
        {
            "id": i,
            "type": "short",
            "text": f"Q{i}",
            "options": [],
            "correct_answer": None,
            "reference_answer": f"Reference {i}",
            "rubric_points": ["point one"],
        }
        for i in range(8, 11)
    )
    return TestContent.model_validate({"questions": questions})


def _short_grade(score_8=0, score_9=0, score_10=0):
    return ShortGradeResult(items=[
        {"id": 8, "score": score_8, "feedback": "feedback 8"},
        {"id": 9, "score": score_9, "feedback": "feedback 9"},
        {"id": 10, "score": score_10, "feedback": "feedback 10"},
    ])


def test_set_complete_updates_milestone(client, db_session):
    task = _build_task(db_session)
    res = client.patch(f"/api/tasks/{task.id}", json={"completed": True})
    assert res.status_code == 200
    db_session.refresh(task)
    assert task.status == "done"
    assert task.milestone.status == "done"


def test_verification_test_flow(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")

    def fake_generate_test(title, desc, previous_question_texts=None, client=None):
        return _quiz_content()

    def fake_grade_short_answers(title, desc, content, answers, client=None):
        return _short_grade(10, 10, 10)

    monkeypatch.setattr("app.api.tasks.generate_test", fake_generate_test)
    monkeypatch.setattr("app.api.tasks.grade_short_answers", fake_grade_short_answers)

    start = client.get(f"/api/tasks/{task.id}/verification").json()
    assert start["mode"] == "test"
    assert len(start["content"]["questions"]) == 10
    public_content = json.dumps(start["content"])
    assert "correct_answer" not in public_content
    assert "reference_answer" not in public_content
    assert "rubric_points" not in public_content
    record_id = start["record_id"]

    res = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": record_id, "answers": {str(i): "A" for i in range(1, 8)}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["passed"] is True
    assert body["verified"] is True
    assert body["points"] == 100
    assert body["details"][0]["correct_answer"] == "A"
    db_session.refresh(task)
    assert task.verified is True
    assert task.status == "done"
    assert len(task.verifications) == 1
    assert task.verifications[0].passed is True


def test_verification_test_six_correct_choices_does_not_pass(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")
    monkeypatch.setattr("app.api.tasks.generate_test", lambda *args, **kwargs: _quiz_content())
    monkeypatch.setattr("app.api.tasks.grade_short_answers", lambda *args, **kwargs: _short_grade())

    start = client.get(f"/api/tasks/{task.id}/verification").json()
    answers = {str(i): "A" for i in range(1, 7)} | {"7": "B", "8": "", "9": "", "10": ""}
    response = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": start["record_id"], "answers": answers},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["points"] == 60
    assert body["score"] == 0.6
    assert body["passed"] is False
    assert body["verified"] is False
    db_session.refresh(task)
    assert task.verified is False


def test_verification_test_exactly_seventy_points_passes(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")
    monkeypatch.setattr("app.api.tasks.generate_test", lambda *args, **kwargs: _quiz_content())
    monkeypatch.setattr("app.api.tasks.grade_short_answers", lambda *args, **kwargs: _short_grade())

    start = client.get(f"/api/tasks/{task.id}/verification").json()
    response = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": start["record_id"], "answers": {str(i): "A" for i in range(1, 8)}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["points"] == 70
    assert body["score"] == 0.7
    assert body["passed"] is True
    assert body["verified"] is True


def test_verification_test_grading_failure_rolls_back_without_verifying(
    client, db_session, monkeypatch
):
    task = _build_task(db_session, "learn")
    monkeypatch.setattr("app.api.tasks.generate_test", lambda *args, **kwargs: _quiz_content())

    def fail_grade(*args, **kwargs):
        raise RuntimeError("grading unavailable")

    monkeypatch.setattr("app.api.tasks.grade_short_answers", fail_grade)
    start = client.get(f"/api/tasks/{task.id}/verification").json()
    response = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": start["record_id"], "answers": {str(i): "A" for i in range(1, 8)}},
    )

    assert response.status_code == 502
    db_session.refresh(task)
    record = db_session.get(VerificationRecord, start["record_id"])
    assert task.verified is False
    assert record.result == ""
    assert record.passed is False


def test_start_verification_uses_prior_question_texts(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")
    prior = VerificationRecord(
        task_id=task.id, mode="test", content=_quiz_content().model_dump_json(),
        submission="", result="", passed=False,
    )
    db_session.add(prior)
    db_session.commit()
    captured = {}

    def fake_generate(title, description, previous_question_texts=None, client=None):
        captured["history"] = previous_question_texts
        return _quiz_content()

    monkeypatch.setattr("app.api.tasks.generate_test", fake_generate)
    response = client.get(f"/api/tasks/{task.id}/verification")

    assert response.status_code == 200
    assert captured["history"] == [f"Q{i}" for i in range(1, 11)]


def test_start_verification_generation_failure_rolls_back(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")

    def fail_generate(*args, **kwargs):
        raise RuntimeError("generation unavailable")

    monkeypatch.setattr("app.api.tasks.generate_test", fail_generate)
    response = client.get(f"/api/tasks/{task.id}/verification")

    assert response.status_code == 502
    assert db_session.query(VerificationRecord).filter_by(task_id=task.id).count() == 0


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


def test_verification_delivery_grading_failure_rolls_back(client, db_session, monkeypatch):
    task = _build_task(db_session, "project")
    monkeypatch.setattr(
        "app.api.tasks.generate_deliver_criteria",
        lambda *args, **kwargs: DeliverContent(acceptance_criteria="criterion"),
    )

    def fail_grade(*args, **kwargs):
        raise RuntimeError("grading unavailable")

    monkeypatch.setattr("app.api.tasks.grade_delivery", fail_grade)
    start = client.get(f"/api/tasks/{task.id}/verification").json()
    response = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": start["record_id"], "submission": "work"},
    )

    assert response.status_code == 502
    db_session.refresh(task)
    record = db_session.get(VerificationRecord, start["record_id"])
    assert task.verified is False
    assert record.result == ""
    assert record.passed is False


def test_verification_wrong_record(client, db_session, monkeypatch):
    task = _build_task(db_session, "learn")
    res = client.post(
        f"/api/tasks/{task.id}/verification",
        json={"record_id": 999, "answers": {}},
    )
    assert res.status_code == 400
