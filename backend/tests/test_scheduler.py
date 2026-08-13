from datetime import date

import pytest

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.scheduler.duration import calculate_target_date
from app.scheduler.scheduler import group_tasks, schedule


def _plan(*tasks):
    return PlanSpec(
        strategy="s",
        milestones=[MilestoneSpec(title="M", order=1, tasks=list(tasks))],
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
            MilestoneSpec(title="M1", order=1,
                          tasks=[TaskSpec(title="m1t", type="learn", effort_hours=1.0)]),
            MilestoneSpec(title="M2", order=2,
                          tasks=[TaskSpec(title="m2t", type="learn", effort_hours=1.0)]),
        ],
    )
    result = schedule(plan, date(2026, 8, 13), blocks_per_day=2)
    assert [(r.milestone_index, r.task_index, r.date) for r in result] == [
        (0, 0, date(2026, 8, 13)),
        (1, 0, date(2026, 8, 13)),
    ]


@pytest.mark.parametrize(
    ("start", "value", "unit", "expected"),
    [
        (date(2026, 8, 13), 1, "day", date(2026, 8, 13)),
        (date(2026, 8, 13), 2, "day", date(2026, 8, 14)),
        (date(2026, 8, 13), 1, "week", date(2026, 8, 19)),
        (date(2026, 8, 13), 2, "week", date(2026, 8, 26)),
        (date(2026, 1, 31), 1, "month", date(2026, 2, 27)),
        (date(2024, 1, 31), 1, "month", date(2024, 2, 28)),
        (date(2026, 11, 30), 3, "month", date(2027, 2, 27)),
    ],
)
def test_calculate_target_date(start, value, unit, expected):
    assert calculate_target_date(start, value, unit) == expected


def test_calculate_target_date_rejects_non_positive_value():
    with pytest.raises(ValueError, match="duration_value 蹇呴』涓烘鏁存暟"):
        calculate_target_date(date(2026, 8, 13), 0, "day")


def test_calculate_target_date_rejects_fractional_value():
    with pytest.raises(ValueError, match="duration_value 蹇呴』涓烘鏁存暟"):
        calculate_target_date(date(2026, 8, 13), 1.5, "day")


def test_uniform_schedule_spans_start_through_deadline_including_weekend():
    plan = _plan(
        TaskSpec(title="a"),
        TaskSpec(title="b"),
        TaskSpec(title="c"),
    )
    result = schedule(
        plan,
        date(2026, 8, 14),  # Friday
        end_date=date(2026, 8, 16),  # Sunday
    )
    assert [item.date for item in result] == [
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 16),
    ]


def test_uniform_schedule_allows_multiple_tasks_on_same_day():
    plan = _plan(*(TaskSpec(title=str(i)) for i in range(5)))
    result = schedule(plan, date(2026, 8, 13), end_date=date(2026, 8, 15))
    assert [item.date for item in result] == [
        date(2026, 8, 13),
        date(2026, 8, 13),
        date(2026, 8, 14),
        date(2026, 8, 15),
        date(2026, 8, 15),
    ]


def test_uniform_schedule_single_task_starts_today():
    result = schedule(
        _plan(TaskSpec(title="only")),
        date(2026, 8, 13),
        end_date=date(2026, 9, 13),
    )
    assert [item.date for item in result] == [date(2026, 8, 13)]


def test_uniform_schedule_empty_plan_returns_empty():
    plan = PlanSpec(strategy="s", milestones=[])
    assert schedule(plan, date(2026, 8, 13), end_date=date(2026, 9, 13)) == []


def test_uniform_schedule_rejects_deadline_before_start():
    with pytest.raises(ValueError, match="target_date"):
        schedule(
            _plan(TaskSpec(title="a")),
            date(2026, 8, 13),
            end_date=date(2026, 8, 12),
        )


def test_group_tasks_packs_atomic_tasks_in_order_within_daily_budget():
    plan = _plan(
        TaskSpec(title="a", description="x", effort_hours=0.5),
        TaskSpec(title="b", description="x", effort_hours=1.5),
        TaskSpec(title="c", description="x", effort_hours=1.0),
        TaskSpec(title="d", description="x", effort_hours=1.0),
    )

    assert group_tasks(plan, daily_hours=2.0) == [
        [(0, 0), (0, 1)],
        [(0, 2), (0, 3)],
    ]


def test_capacity_groups_multiple_atomic_tasks_on_one_day_and_spans_deadline():
    plan = _plan(
        TaskSpec(title="a", description="x", effort_hours=0.5),
        TaskSpec(title="b", description="x", effort_hours=1.5),
        TaskSpec(title="c", description="x", effort_hours=1.0),
        TaskSpec(title="d", description="x", effort_hours=1.0),
    )
    result = schedule(
        plan,
        date(2026, 8, 14),
        end_date=date(2026, 8, 16),
        daily_hours=2.0,
    )

    assert [item.date for item in result] == [
        date(2026, 8, 14), date(2026, 8, 14),
        date(2026, 8, 16), date(2026, 8, 16),
    ]
    effort_by_date = {}
    for item in result:
        effort_by_date.setdefault(item.date, 0.0)
        effort_by_date[item.date] += plan.milestones[item.milestone_index].tasks[
            item.task_index
        ].effort_hours
    assert all(effort <= 2.0 for effort in effort_by_date.values())


def test_capacity_grouping_rejects_fragmentation_that_needs_more_days():
    plan = _plan(*[
        TaskSpec(title=str(i), description="x", effort_hours=effort)
        for i, effort in enumerate([1.5, 1.5, 1.0])
    ])

    with pytest.raises(ValueError, match="3 个自然日"):
        schedule(
            plan,
            date(2026, 8, 13),
            end_date=date(2026, 8, 14),
            daily_hours=2.0,
        )


def test_capacity_schedule_preserves_flattened_order_across_milestones():
    plan = PlanSpec(
        strategy="s",
        milestones=[
            MilestoneSpec(
                title="M1",
                order=1,
                tasks=[TaskSpec(title="a", description="x", effort_hours=1.5)],
            ),
            MilestoneSpec(
                title="M2",
                order=2,
                tasks=[
                    TaskSpec(title="b", description="x", effort_hours=0.5),
                    TaskSpec(title="c", description="x", effort_hours=1.0),
                ],
            ),
        ],
    )

    result = schedule(
        plan,
        date(2026, 8, 14),
        end_date=date(2026, 8, 16),
        daily_hours=2.0,
    )

    assert [(item.milestone_index, item.task_index) for item in result] == [
        (0, 0),
        (1, 0),
        (1, 1),
    ]
    assert [item.date for item in result] == [
        date(2026, 8, 14),
        date(2026, 8, 14),
        date(2026, 8, 16),
    ]
