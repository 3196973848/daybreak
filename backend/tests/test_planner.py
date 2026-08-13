from app.llm.planner import generate_plan
from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec


class FakeResponse:
    def __init__(self, parsed):
        self.parsed_output = parsed


class FakeMessages:
    def __init__(self, spec):
        self._spec = spec

    def parse(self, **kwargs):
        return FakeResponse(self._spec)


class FakeClient:
    def __init__(self, spec):
        self.messages = FakeMessages(spec)


def test_generate_plan_returns_spec():
    spec = PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="里程碑1", order=1, target_date_offset_days=7,
            tasks=[TaskSpec(title="任务1", type="learn", effort_hours=1.0)],
        )],
    )
    client = FakeClient(spec)
    got = generate_plan("目标", "说明", "2026-11-13", client=client)
    assert got == spec
    assert got.milestones[0].tasks[0].type == "learn"
