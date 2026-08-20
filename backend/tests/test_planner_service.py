import json
from datetime import date, timedelta

import pytest

from app.llm.planner import parse_plan_spec
from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.models import Goal
from app.services.capacity import InsufficientCapacityError
from app.services.planner_service import create_goal_with_plan


def _fake_spec():
    return PlanSpec(
        strategy="策略",
        milestones=[
            MilestoneSpec(
                title="里程碑1", order=1,
                tasks=[
                    TaskSpec(
                        title="任务1", description="成果1",
                        type="learn", effort_hours=1.0,
                    ),
                    TaskSpec(
                        title="任务2", description="成果2",
                        type="practice", effort_hours=2.0,
                    ),
                ],
            ),
        ],
    )


def _three_task_spec():
    return PlanSpec(
        strategy="均匀学习",
        milestones=[
            MilestoneSpec(
                title="阶段一",
                order=1,
                tasks=[
                    TaskSpec(title="任务1", description="成果1"),
                    TaskSpec(title="任务2", description="成果2"),
                ],
            ),
            MilestoneSpec(
                title="阶段二",
                order=2,
                tasks=[TaskSpec(title="任务3", description="成果3")],
            ),
        ],
    )


def _plan_with_efforts(*efforts):
    return PlanSpec(
        strategy="原子计划",
        milestones=[
            MilestoneSpec(
                title="阶段",
                order=1,
                tasks=[
                    TaskSpec(
                        title=f"任务{index}",
                        description=f"成果{index}",
                        effort_hours=effort,
                    )
                    for index, effort in enumerate(efforts, start=1)
                ],
            )
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
    # target_date is updated to actual last scheduled task date
    # Tasks are packed into consecutive days
    assert [task.scheduled_date for ms in goal.plan.milestones for task in ms.tasks] == [
        start,
        start,
        start + timedelta(days=1),
    ]
    assert goal.target_date == start + timedelta(days=1)
    assert [ms.due_date for ms in goal.plan.milestones] == [
        start,
        start + timedelta(days=1),
    ]


def test_legacy_target_date_also_uses_uniform_schedule(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _three_task_spec()
    )
    start = date.today()
    target = start + timedelta(days=8)
    goal = create_goal_with_plan(db_session, "目标", target_date=target)
    # Tasks are packed into consecutive days, not spread across deadline
    assert [task.scheduled_date for ms in goal.plan.milestones for task in ms.tasks] == [
        start,
        start,
        start + timedelta(days=1),
    ]


def test_deadline_empty_milestones_inherit_previous_nonempty_due_or_start(
    db_session, monkeypatch
):
    spec = PlanSpec(
        strategy="均匀学习",
        milestones=[
            MilestoneSpec(title="前置空阶段", order=1, tasks=[]),
            MilestoneSpec(
                title="阶段一",
                order=2,
                tasks=[TaskSpec(title="任务一")],
            ),
            MilestoneSpec(title="中间空阶段", order=3, tasks=[]),
            MilestoneSpec(
                title="阶段二",
                order=4,
                tasks=[TaskSpec(title="任务二")],
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: spec
    )
    monkeypatch.setattr(
        "app.services.planner_service.validate_atomic_plan", lambda *a, **k: None
    )
    start = date.today()
    target = start + timedelta(days=8)

    goal = create_goal_with_plan(db_session, "目标", target_date=target)

    assert [milestone.due_date for milestone in goal.plan.milestones] == [
        start,
        start,
        start,
        start,
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
        "app.services.planner_service.generate_plan", lambda *a, **k: _fake_spec()
    )
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


def test_refresh_failure_rolls_back_and_leaves_session_usable(
    db_session, monkeypatch
):
    original_refresh = db_session.refresh

    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: _fake_spec()
    )
    monkeypatch.setattr(
        db_session,
        "refresh",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("refresh failed")),
    )

    with pytest.raises(RuntimeError, match="refresh failed"):
        create_goal_with_plan(db_session, "goal")

    assert db_session.query(Goal).count() == 0

    monkeypatch.setattr(db_session, "refresh", original_refresh)
    db_session.add(Goal(title="recovered"))
    db_session.commit()
    assert db_session.query(Goal).filter_by(title="recovered").one() is not None


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


def test_invalid_atomic_plan_is_regenerated_with_feedback(db_session, monkeypatch):
    invalid = _plan_with_efforts(3.0)
    valid = _plan_with_efforts(1.0, 1.0)
    calls = []

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return invalid if len(calls) == 1 else valid

    monkeypatch.setattr("app.services.planner_service.generate_plan", fake)
    goal = create_goal_with_plan(
        db_session,
        "学习交易",
        duration_value=2,
        duration_unit="day",
        daily_hours=2.0,
    )

    assert goal.id is not None
    assert len(calls) == 2
    assert calls[0]["daily_hours"] == 2.0
    assert calls[0]["feedback"] is None
    assert "超过每日投入时间" in calls[1]["feedback"]


def test_invalid_atomic_plan_stops_after_three_attempts_and_rolls_back(
    db_session, monkeypatch
):
    calls = []

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return _plan_with_efforts(3.0)

    monkeypatch.setattr("app.services.planner_service.generate_plan", fake)

    with pytest.raises(RuntimeError, match="无法生成有效的原子计划"):
        create_goal_with_plan(db_session, "学习交易", daily_hours=2.0)

    assert len(calls) == 3
    assert db_session.query(Goal).count() == 0


@pytest.mark.parametrize(
    "invalid_message",
    ["LLM 返回为空", "LLM 输出不是合法 JSON", "LLM 输出不符合结构"],
    ids=["empty", "malformed-json", "schema-invalid"],
)
def test_invalid_model_output_is_regenerated_with_safe_feedback(
    db_session, monkeypatch, invalid_message
):
    calls = []
    sentinel = "PRIVATE_MODEL_OUTPUT_SENTINEL"

    def fake(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError(f"{invalid_message}: {sentinel}")
        return _plan_with_efforts(1.0)

    monkeypatch.setattr("app.services.planner_service.generate_plan", fake)
    goal = create_goal_with_plan(db_session, "学习交易", daily_hours=2.0)

    assert goal.id is not None
    assert len(calls) == 2
    assert calls[1]["feedback"] == (
        "上次模型输出为空、不是合法 JSON 或不符合计划结构；"
        "请只返回符合约定结构的完整 JSON 计划"
    )
    assert sentinel not in calls[1]["feedback"]


def test_three_invalid_model_outputs_fail_safely_and_roll_back(db_session, monkeypatch):
    calls = []
    sentinel = "PRIVATE_MODEL_OUTPUT_SENTINEL"

    def fake(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError(f"invalid model output: {sentinel}")

    monkeypatch.setattr("app.services.planner_service.generate_plan", fake)

    with pytest.raises(RuntimeError, match="无法生成有效的原子计划") as caught:
        create_goal_with_plan(db_session, "学习交易", daily_hours=2.0)

    assert len(calls) == 3
    assert [call["feedback"] for call in calls] == [
        None,
        "上次模型输出为空、不是合法 JSON 或不符合计划结构；"
        "请只返回符合约定结构的完整 JSON 计划",
        "上次模型输出为空、不是合法 JSON 或不符合计划结构；"
        "请只返回符合约定结构的完整 JSON 计划",
    ]
    assert sentinel not in str(caught.value)
    assert db_session.query(Goal).count() == 0


@pytest.mark.parametrize("invalid_kind", ["unsupported_type", "date_extra"])
def test_schema_invalid_model_plan_is_regenerated(
    db_session, monkeypatch, invalid_kind
):
    invalid = _plan_with_efforts(1.0).model_dump()
    task_payload = invalid["milestones"][0]["tasks"][0]
    if invalid_kind == "unsupported_type":
        task_payload["type"] = "study"
    else:
        task_payload["scheduled_date"] = "2026-08-15"
    payloads = [invalid, _plan_with_efforts(1.0).model_dump()]
    calls = []

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return parse_plan_spec(json.dumps(payloads.pop(0)))

    monkeypatch.setattr("app.services.planner_service.generate_plan", fake)
    goal = create_goal_with_plan(db_session, "学习交易", daily_hours=2.0)

    assert goal.id is not None
    assert len(calls) == 2
    assert goal.plan.milestones[0].tasks[0].type == "learn"


def test_capacity_shortage_rolls_back_and_reports_suggestion(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan",
        lambda *a, **k: _plan_with_efforts(1.5, 1.5, 1.0),
    )

    with pytest.raises(InsufficientCapacityError) as caught:
        create_goal_with_plan(
            db_session,
            "目标",
            duration_value=2,
            duration_unit="day",
            daily_hours=2.0,
        )

    assert caught.value.required_hours == 4.0
    assert caught.value.available_hours == 4.0
    assert caught.value.minimum_days == 3
    assert caught.value.suggested_duration == {"value": 3, "unit": "day"}
    assert db_session.query(Goal).count() == 0


def test_same_day_tasks_share_dates_and_milestones_use_final_task_dates(
    db_session, monkeypatch
):
    spec = PlanSpec(
        strategy="分组计划",
        milestones=[
            MilestoneSpec(
                title="阶段一",
                order=1,
                tasks=[
                    TaskSpec(title="任务1", description="成果1", effort_hours=0.5),
                    TaskSpec(title="任务2", description="成果2", effort_hours=1.5),
                ],
            ),
            MilestoneSpec(
                title="阶段二",
                order=2,
                tasks=[
                    TaskSpec(title="任务3", description="成果3", effort_hours=1.0),
                    TaskSpec(title="任务4", description="成果4", effort_hours=1.0),
                ],
            ),
        ],
    )
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan", lambda *a, **k: spec
    )
    start = date.today()

    goal = create_goal_with_plan(
        db_session,
        "目标",
        duration_value=2,
        duration_unit="day",
        daily_hours=2.0,
    )

    assert [[task.scheduled_date for task in ms.tasks] for ms in goal.plan.milestones] == [
        [start, start],
        [start + timedelta(days=1), start + timedelta(days=1)],
    ]
    assert [ms.due_date for ms in goal.plan.milestones] == [
        ms.tasks[-1].scheduled_date for ms in goal.plan.milestones
    ]
