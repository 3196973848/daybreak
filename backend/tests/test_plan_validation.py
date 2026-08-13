import pytest

from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.services.plan_validation import PlanValidationError, validate_atomic_plan


def plan_with(*efforts):
    return PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="交易规则领域",
            order=1,
            tasks=[
                TaskSpec(
                    title=f"知识点{i}",
                    description="明确成果",
                    effort_hours=effort,
                )
                for i, effort in enumerate(efforts)
            ],
        )],
    )


def test_atomic_plan_accepts_half_hour_tasks_within_daily_budget():
    validate_atomic_plan(plan_with(0.5, 1.0, 2.0), daily_hours=2.0)


@pytest.mark.parametrize("effort", [0, -0.5, 0.75, 2.5])
def test_atomic_plan_rejects_invalid_effort_or_task_over_budget(effort):
    with pytest.raises(PlanValidationError):
        validate_atomic_plan(plan_with(effort), daily_hours=2.0)


@pytest.mark.parametrize(
    "plan",
    [
        PlanSpec(strategy="策略", milestones=[]),
        PlanSpec(
            strategy="策略",
            milestones=[MilestoneSpec(title=" ", order=1, tasks=[])],
        ),
        PlanSpec(
            strategy="策略",
            milestones=[MilestoneSpec(
                title="领域",
                order=1,
                tasks=[TaskSpec(title=" ", description="成果", effort_hours=0.5)],
            )],
        ),
        PlanSpec(
            strategy="策略",
            milestones=[MilestoneSpec(
                title="领域",
                order=1,
                tasks=[TaskSpec(title="知识点", description=" ", effort_hours=0.5)],
            )],
        ),
    ],
)
def test_atomic_plan_rejects_missing_domain_or_task_details(plan):
    with pytest.raises(PlanValidationError):
        validate_atomic_plan(plan, daily_hours=2.0)


@pytest.mark.parametrize("daily_hours", [0, -1, float("nan"), float("inf")])
def test_atomic_plan_rejects_invalid_daily_budget(daily_hours):
    with pytest.raises(PlanValidationError):
        validate_atomic_plan(plan_with(0.5), daily_hours=daily_hours)
