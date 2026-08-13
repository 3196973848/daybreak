import math

from ..llm.schema import PlanSpec


class PlanValidationError(ValueError):
    pass


def validate_atomic_plan(plan: PlanSpec, daily_hours: float) -> None:
    if not math.isfinite(daily_hours) or daily_hours <= 0:
        raise PlanValidationError("每日预算必须是有限的正数")
    if not plan.milestones:
        raise PlanValidationError("计划必须包含至少一个领域")
    for milestone in plan.milestones:
        if not milestone.title.strip() or not milestone.tasks:
            raise PlanValidationError("每个领域必须有标题和原子任务")
        for task in milestone.tasks:
            if not task.title.strip() or not task.description.strip():
                raise PlanValidationError("原子任务必须有具体标题和成果描述")
            effort = task.effort_hours
            if not math.isfinite(effort) or effort < 0.5 or effort > daily_hours:
                raise PlanValidationError("任务耗时必须在 0.5 小时与每日预算之间")
            if not math.isclose(effort * 2, round(effort * 2)):
                raise PlanValidationError("任务耗时必须以 0.5 小时递增")
