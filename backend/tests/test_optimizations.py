"""Tests for all optimization features: replan, pace, preview, ical, review, remedy"""
from datetime import date, datetime, timedelta
from unittest.mock import patch

from app.models import Goal, Milestone, Plan, Task, VerificationRecord


def _build_goal(db_session, task_count=4, completed_count=0, with_actual=False):
    user = db_session.query_by(type).filter_by(username="tester").one() if hasattr(db_session, 'query_by') else None
    from app.models import User
    user = db_session.query(User).filter_by(username="tester").one()

    goal = Goal(title="学习Python", description="从零开始", target_date=date.today() + timedelta(days=30), user_id=user.id)
    db_session.add(goal)
    db_session.flush()
    plan = Plan(goal_id=goal.id, strategy="分阶段学习")
    db_session.add(plan)
    db_session.flush()
    ms = Milestone(plan_id=plan.id, title="基础入门", order=1)
    db_session.add(ms)
    db_session.flush()

    today = date.today()
    for i in range(task_count):
        t = Task(
            milestone_id=ms.id, title=f"任务{i+1}", description=f"描述{i+1}",
            type="learn", effort=1.0, order=i,
            scheduled_date=today + timedelta(days=i),
            status="done" if i < completed_count else "todo",
            completed_at=datetime.now() if i < completed_count else None,
            actual_minutes=90 if (with_actual and i < completed_count) else None,
        )
        db_session.add(t)

    db_session.commit()
    db_session.refresh(goal)
    return goal


# --- P0-1: Replan ---

def test_replan_partial_complete(client, db_session):
    goal = _build_goal(db_session, task_count=4, completed_count=2)
    res = client.post(f"/api/goals/{goal.id}/replan")
    assert res.status_code == 200
    body = res.json()
    tasks = body["plan"]["milestones"][0]["tasks"]
    assert tasks[0]["status"] == "done"
    assert tasks[1]["status"] == "done"
    assert tasks[2]["status"] == "todo"
    assert tasks[3]["status"] == "todo"


def test_replan_all_incomplete(client, db_session):
    goal = _build_goal(db_session, task_count=3, completed_count=0)
    res = client.post(f"/api/goals/{goal.id}/replan")
    assert res.status_code == 200
    for t in res.json()["plan"]["milestones"][0]["tasks"]:
        assert t["scheduled_date"] is not None


def test_replan_all_done(client, db_session):
    goal = _build_goal(db_session, task_count=2, completed_count=2)
    res = client.post(f"/api/goals/{goal.id}/replan")
    assert res.status_code == 200


def test_replan_not_found(client, db_session):
    res = client.post("/api/goals/999/replan")
    assert res.status_code == 404


def test_replan_insufficient_capacity(client, db_session):
    goal = _build_goal(db_session, task_count=10, completed_count=0)
    goal.target_date = date.today() + timedelta(days=1)
    db_session.commit()
    res = client.post(f"/api/goals/{goal.id}/replan")
    assert res.status_code in (404, 422, 500)  # capacity/validation error


# --- P0-2: Pace ---

def test_pace_basic(client, db_session):
    goal = _build_goal(db_session, task_count=4, completed_count=2, with_actual=True)
    res = client.get(f"/api/goals/{goal.id}/pace")
    assert res.status_code == 200
    body = res.json()
    assert body["total_tasks"] == 4
    assert body["completed_tasks"] == 2
    assert body["actual_hours"] == 3.0  # 2 * 90min


def test_pace_no_tasks(client, db_session):
    goal = _build_goal(db_session, task_count=0, completed_count=0)
    res = client.get(f"/api/goals/{goal.id}/pace")
    assert res.status_code == 200
    assert res.json()["total_tasks"] == 0


def test_pace_not_found(client, db_session):
    res = client.get("/api/goals/999/pace")
    assert res.status_code == 404


# --- P0-2: actual_minutes ---

def test_task_complete_with_actual_minutes(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=0)
    task = goal.plan.milestones[0].tasks[0]
    res = client.patch(f"/api/tasks/{task.id}", json={"completed": True, "actual_minutes": 45})
    assert res.status_code == 200
    assert res.json()["actual_minutes"] == 45


def test_task_uncomplete_clears_actual(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=1, with_actual=True)
    task = goal.plan.milestones[0].tasks[0]
    res = client.patch(f"/api/tasks/{task.id}", json={"completed": False})
    assert res.status_code == 200
    assert res.json()["actual_minutes"] is None


# --- P1-1: Preview ---

def test_preview_returns_assumptions(client, db_session):
    with patch("app.api.goals.preview_goal") as mock:
        from app.llm.schema import PreviewSpec, MilestoneSpec, TaskSpec
        mock.return_value = PreviewSpec(
            strategy="分阶段",
            assumptions=["假设1", "假设2"],
            milestones=[MilestoneSpec(title="M1", order=1, tasks=[TaskSpec(title="T1")])],
        )
        res = client.post("/api/goals/preview", json={"title": "测试"})
        assert res.status_code == 200
        body = res.json()
        assert len(body["assumptions"]) == 2
        assert body["strategy"] == "分阶段"


def test_preview_does_not_write_db(client, db_session):
    with patch("app.api.goals.preview_goal") as mock:
        from app.llm.schema import PreviewSpec
        mock.return_value = PreviewSpec(strategy="s", assumptions=[], milestones=[])
        client.post("/api/goals/preview", json={"title": "测试"})
        goals = db_session.query(Goal).all()
        assert len(goals) == 0


def test_create_with_rejected_assumptions(client, db_session):
    with patch("app.api.goals.create_goal_with_plan") as mock:
        goal = _build_goal(db_session, task_count=1, completed_count=0)
        mock.return_value = goal
        res = client.post("/api/goals", json={"title": "测试", "rejected_assumptions": ["假设1"]})
        assert res.status_code == 201
        call_kwargs = mock.call_args.kwargs
        assert call_kwargs["rejected_assumptions"] == ["假设1"]


# --- P1-2: iCal ---

def test_calendar_ics_with_token(client, db_session):
    goal = _build_goal(db_session, task_count=2, completed_count=1)
    db_session.refresh(goal)
    res = client.get(f"/api/goals/{goal.id}/calendar.ics?token={goal.feed_token}")
    assert res.status_code == 200
    content = res.text
    assert "BEGIN:VCALENDAR" in content
    assert "任务1" in content
    assert "STATUS:COMPLETED" in content
    assert "STATUS:TENTATIVE" in content


def test_calendar_ics_invalid_token(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=0)
    res = client.get(f"/api/goals/{goal.id}/calendar.ics?token=wrong")
    assert res.status_code == 401


def test_calendar_ics_no_token(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=0)
    res = client.get(f"/api/goals/{goal.id}/calendar.ics")
    assert res.status_code == 401


def test_goal_has_feed_token(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=0)
    res = client.get(f"/api/goals/{goal.id}")
    assert res.status_code == 200
    assert "feed_token" in res.json()
    assert len(res.json()["feed_token"]) > 10


# --- P2-2: Review ---

def test_review_current_week(client, db_session):
    goal = _build_goal(db_session, task_count=5, completed_count=3)
    res = client.get(f"/api/goals/{goal.id}/review")
    assert res.status_code == 200
    body = res.json()
    assert body["total_planned"] == 5
    assert body["total_completed"] == 3
    assert body["completion_rate"] == 60.0
    assert len(body["daily"]) == 7
    assert "conclusion" in body


def test_review_specific_week(client, db_session):
    goal = _build_goal(db_session, task_count=3, completed_count=1)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_str = f"{monday.isocalendar()[0]}-{monday.isocalendar()[1]:02d}"
    res = client.get(f"/api/goals/{goal.id}/review?week={week_str}")
    assert res.status_code == 200


def test_review_empty_week(client, db_session):
    goal = _build_goal(db_session, task_count=2, completed_count=0)
    res = client.get(f"/api/goals/{goal.id}/review?week=2020-01")
    assert res.status_code == 200
    assert res.json()["total_planned"] == 0


def test_review_not_found(client, db_session):
    res = client.get("/api/goals/999/review")
    assert res.status_code == 404


def test_review_invalid_week(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=0)
    res = client.get(f"/api/goals/{goal.id}/review?week=invalid")
    assert res.status_code == 400


# --- P2-1: Remedy ---

def test_remedy_on_verification_failure(client, db_session):
    goal = _build_goal(db_session, task_count=1, completed_count=0)
    task = goal.plan.milestones[0].tasks[0]

    # Create a verification record
    record = VerificationRecord(
        task_id=task.id, mode="deliver",
        content='{"acceptance_criteria": "test"}',
        submission="", result="", passed=False,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    with patch("app.api.tasks.grade_delivery") as mock_grade, \
         patch("app.api.tasks.generate_remedy_tasks") as mock_remedy:
        from app.llm.verifier import GradeResult, RemedyResult, RemedyTask
        mock_grade.return_value = GradeResult(score=0.3, feedback="理解有误")
        mock_remedy.return_value = RemedyResult(tasks=[
            RemedyTask(title="补强任务1", description="复习"),
        ])

        res = client.post(f"/api/tasks/{task.id}/verification", json={
            "record_id": record.id, "submission": "bad",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["passed"] is False
        assert len(body.get("remedy_tasks", [])) == 1
