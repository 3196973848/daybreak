import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Goal,
    LearningSession,
    LearningTurn,
    Milestone,
    Plan,
    Task,
    VerificationRecord,
)


def _learning_task(db_session):
    goal = Goal(title="学习目标", description="说明")
    db_session.add(goal)
    plan = Plan(goal_id=0, strategy="策略")
    goal.plan = plan
    milestone = Milestone(title="里程碑", order=1)
    plan.milestones.append(milestone)
    task = Task(title="任务", type="learn", order=0, effort=1.0)
    milestone.tasks.append(task)
    return task


def test_goal_tree_roundtrip(db_session):
    goal = Goal(title="目标", description="说明")
    db_session.add(goal)
    plan = Plan(goal_id=0, strategy="策略")
    goal.plan = plan
    ms = Milestone(title="里程碑1", order=1)
    plan.milestones.append(ms)
    t = Task(title="任务1", type="learn", order=0, effort=1.0)
    ms.tasks.append(t)
    t.verifications.append(VerificationRecord(mode="test", content="{}"))
    db_session.commit()

    got = db_session.get(Goal, goal.id)
    assert got.plan.strategy == "策略"
    assert got.plan.milestones[0].tasks[0].title == "任务1"
    assert got.plan.milestones[0].tasks[0].verifications[0].mode == "test"


def test_learning_session_roundtrip_and_turn_order(db_session):
    task = _learning_task(db_session)
    task.learning_session = LearningSession(
        stage="explain",
        session_summary="已诊断基础",
        covered_points=json.dumps(["规则定义"], ensure_ascii=False),
        weak_points=json.dumps(["边界条件"], ensure_ascii=False),
        ready_for_verification=False,
        estimated_hours_snapshot=2.0,
        turns=[
            LearningTurn(
                client_turn_id="initial",
                user_message=None,
                assistant_message="你目前如何理解这条规则？",
                stage="diagnose",
            ),
            LearningTurn(
                client_turn_id="turn-1",
                user_message="我理解为…",
                assistant_message="先澄清定义。",
                stage="explain",
            ),
        ],
    )
    db_session.commit()
    db_session.expire_all()

    got = db_session.get(Task, task.id).learning_session
    assert got.estimated_hours_snapshot == 2.0
    assert [turn.client_turn_id for turn in got.turns] == ["initial", "turn-1"]
    assert json.loads(got.covered_points) == ["规则定义"]


def test_learning_session_and_client_turn_ids_are_unique(db_session):
    first_task = _learning_task(db_session)
    first_task.learning_session = LearningSession(
        estimated_hours_snapshot=1.0,
        turns=[
            LearningTurn(
                client_turn_id="same-id",
                user_message=None,
                assistant_message="诊断",
                stage="diagnose",
            )
        ],
    )
    db_session.commit()

    db_session.add(
        LearningTurn(
            session_id=first_task.learning_session.id,
            client_turn_id="same-id",
            user_message="重复",
            assistant_message="不应保存",
            stage="explain",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
