from app.models import Goal, Milestone, Plan, Task, VerificationRecord


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
