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
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Resp", (), {"choices": [FakeChoice(self._content)]})()


class FakeClient:
    def __init__(self, content):
        self.chat = type("Chat", (), {"completions": FakeCompletions(content)})()


def test_generate_plan_returns_spec():
    spec = PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="里程碑1", order=1,
            tasks=[TaskSpec(title="任务1", type="learn", effort_hours=1.0)],
        )],
    )
    client = FakeClient(spec.model_dump_json())
    got = generate_plan("目标", "说明", "2026-11-13", client=client)
    assert got == spec
    assert got.milestones[0].tasks[0].type == "learn"


def test_generate_plan_requests_atomic_tasks_within_daily_budget_without_dates():
    spec = PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="交易规则领域",
            order=1,
            tasks=[TaskSpec(
                title="价格优先规则",
                description="解释价格优先如何决定撮合顺序",
                effort_hours=0.5,
            )],
        )],
    )
    client = FakeClient(spec.model_dump_json())

    generate_plan("学习交易", "", "2026-09-11", daily_hours=2.5, client=client)

    prompt = json.dumps(client.chat.completions.calls[0]["messages"], ensure_ascii=False)
    assert "2.5" in prompt
    assert "自动识别" in prompt
    assert "具体子知识点" in prompt
    assert "0.5" in prompt
    assert "不要输出日期" in prompt


def test_generate_plan_includes_validation_feedback_for_regeneration():
    spec = PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="领域",
            tasks=[TaskSpec(title="知识点", description="成果", effort_hours=0.5)],
        )],
    )
    client = FakeClient(spec.model_dump_json())

    generate_plan(
        "学习交易",
        "",
        None,
        feedback="任务耗时超过每日预算",
        client=client,
    )

    prompt = json.dumps(client.chat.completions.calls[0]["messages"], ensure_ascii=False)
    assert "上次计划校验失败：任务耗时超过每日预算" in prompt
    assert "请修正后重新生成完整计划" in prompt


def test_generate_plan_handles_invalid_json():
    client = FakeClient("这不是 JSON")
    try:
        generate_plan("目标", "说明", None, client=client)
        assert False, "should raise"
    except RuntimeError as exc:
        assert "JSON" in str(exc)
