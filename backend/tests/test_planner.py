import json

from app.llm.planner import generate_plan
from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return type("Resp", (), {"choices": [FakeChoice(self._content)]})()


class FakeClient:
    def __init__(self, content):
        self.chat = type("Chat", (), {"completions": FakeCompletions(content)})()


def test_generate_plan_returns_spec():
    spec = PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="里程碑1", order=1, target_date_offset_days=7,
            tasks=[TaskSpec(title="任务1", type="learn", effort_hours=1.0)],
        )],
    )
    client = FakeClient(spec.model_dump_json())
    got = generate_plan("目标", "说明", "2026-11-13", client=client)
    assert got == spec
    assert got.milestones[0].tasks[0].type == "learn"


def test_generate_plan_handles_invalid_json():
    client = FakeClient("这不是 JSON")
    try:
        generate_plan("目标", "说明", None, client=client)
        assert False, "should raise"
    except RuntimeError as exc:
        assert "JSON" in str(exc)
