from datetime import date, timedelta

import pytest

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.models import Goal
from app.services.planner_service import create_goal_with_plan


def _fake_spec():
    return PlanSpec(
        strategy="策略",
        milestones=[
            MilestoneSpec(
                title="里程碑1", order=1,
                tasks=[
                    TaskSpec(title="任务1", type="learn", effort_hours=1.0),
                    TaskSpec(title="任务2", type="practice", effort_hours=2.0),
                ],
            ),
            MilestoneSpec(title="空里程碑", order=2, tasks=[]),
        ],
    )


def _three_task_spec():
    return PlanSpec(
        strategy="均匀学习",
        milestones=[
            MilestoneSpec(
                title="阶段一",
                order=1,
                tasks=[TaskSpec(title="任务1"), TaskSpec(title="任务2")],
            ),
            MilestoneSpec(
                title="阶段二",
                order=2,
                tasks=[TaskSpec(title="任务3")],
            ),
            MilestoneSpec(
                title="空阶段",
                order=3,
                tasks=[],
            ),
        ],
    )


def test_duration_persists_deadline_and_uses_uniform_task_and_milestone_dates(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _three_task_spec()
    )
    start = date.today()
    goal = create_goal_with_plan(
        db_session,
        "目标",
        duration_value=10,
        duration_unit="day",
    )
    assert goal.target_date == start + timedelta(days=9)
    assert [task.scheduled_date for ms in goal.plan.milestones for task in ms.tasks] == [
        start,
        start + timedelta(days=4),
        start + timedelta(days=9),
    ]
    assert [ms.due_date for ms in goal.plan.milestones] == [
        start + timedelta(days=4),
        start + timedelta(days=9),
        start + timedelta(days=9),
    ]


def test_legacy_target_date_also_uses_uniform_schedule(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _three_task_spec()
    )
    start = date.today()
    target = start + timedelta(days=8)
    goal = create_goal_with_plan(db_session, "目标", target_date=target)
    assert [task.scheduled_date for ms in goal.plan.milestones for task in ms.tasks] == [
        start,
        start + timedelta(days=4),
        target,
    ]


def test_initial_goal_flush_failure_rolls_back_and_leaves_session_usable(
    db_session, monkeypatch
):
    rollback_calls = []
    original_rollback = db_session.rollback
    original_flush = db_session.flush

    def rollback():
        rollback_calls.append(True)
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", rollback)
    monkeypatch.setattr(
        db_session, "flush", lambda: (_ for _ in ()).throw(RuntimeError("flush failed"))
    )

    with pytest.raises(RuntimeError, match="flush failed"):
        create_goal_with_plan(db_session, "目标")

    assert rollback_calls == [True]
    monkeypatch.setattr(db_session, "flush", original_flush)
    db_session.add(Goal(title="可恢复"))
    db_session.commit()
    assert db_session.query(Goal).filter_by(title="可恢复").one() is not None


def test_create_goal_persists_full_tree(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _fake_spec()
    )
    goal = create_goal_with_plan(db_session, "目标", "说明")
    db_session.refresh(goal)
    assert goal.plan is not None
    ms = goal.plan.milestones[0]
    assert ms.title == "里程碑1"
    assert ms.due_date == date.today() + timedelta(days=1)
    assert len(ms.tasks) == 2
    assert ms.tasks[0].scheduled_date == date.today()
    assert ms.tasks[1].scheduled_date == date.today() + timedelta(days=1)
    assert ms.tasks[1].verified is False
    assert goal.plan.milestones[1].due_date == ms.due_date
