from datetime import date, timedelta

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.models import Goal
from app.services.planner_service import create_goal_with_plan


def _fake_spec():
    return PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="里程碑1", order=1, target_date_offset_days=7,
            tasks=[
                TaskSpec(title="任务1", type="learn", effort_hours=1.0),
                TaskSpec(title="任务2", type="practice", effort_hours=2.0),
            ],
        )],
    )


def test_create_goal_persists_full_tree(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _fake_spec()
    )
    goal = create_goal_with_plan(db_session, "目标", "说明", date(2026, 11, 13))
    db_session.refresh(goal)
    assert goal.plan is not None
    ms = goal.plan.milestones[0]
    assert ms.title == "里程碑1"
    assert ms.due_date == date.today() + timedelta(days=7)  # start=today + 7 offset
    assert len(ms.tasks) == 2
    # 任务1(1h)+任务2(2h),每天2块 → 任务2 顺延到次日
    assert ms.tasks[0].scheduled_date == date.today()
    assert ms.tasks[1].scheduled_date == date.today() + timedelta(days=1)
    assert ms.tasks[1].verified is False
