from datetime import date

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.scheduler.scheduler import schedule


def _plan(*tasks):
    return PlanSpec(
        strategy="s",
        milestones=[MilestoneSpec(title="M", order=1, target_date_offset_days=7, tasks=list(tasks))],
    )


def test_tasks_fit_in_one_day():
    plan = _plan(
        TaskSpec(title="a", type="learn", effort_hours=1.0),
        TaskSpec(title="b", type="learn", effort_hours=1.0),
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [r.date for r in result] == [date(2026, 8, 13), date(2026, 8, 13)]


def test_task_overflows_to_next_day():
    plan = _plan(
        TaskSpec(title="a", type="learn", effort_hours=1.0),
        TaskSpec(title="b", type="project", effort_hours=3.0),
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [r.date for r in result] == [date(2026, 8, 13), date(2026, 8, 14)]


def test_respects_milestone_order_and_index():
    plan = PlanSpec(
        strategy="s",
        milestones=[
            MilestoneSpec(title="M1", order=1, target_date_offset_days=3,
                          tasks=[TaskSpec(title="m1t", type="learn", effort_hours=1.0)]),
            MilestoneSpec(title="M2", order=2, target_date_offset_days=7,
                          tasks=[TaskSpec(title="m2t", type="learn", effort_hours=1.0)]),
        ],
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [(r.milestone_order, r.task_index, r.date) for r in result] == [
        (1, 0, date(2026, 8, 13)),
        (2, 0, date(2026, 8, 13)),
    ]
