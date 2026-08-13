# Task 4: LLM 计划生成模块

## 目标

实现 `generate_plan()`:调 Anthropic SDK 的 `client.messages.parse(..., output_format=PlanSpec)` 生成计划;用 fake client 单测。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 4** 一节。

## 要创建的文件

- `backend/app/llm/planner.py`
- `backend/tests/test_planner.py`

## 关键接口(后续任务依赖,必须一致)

```python
def generate_plan(goal_title: str, description: str, target_date: str | None,
                  client: anthropic.Anthropic | None = None) -> PlanSpec
```

- `client` 默认 `None`,内部 `client = client or anthropic.Anthropic()`
- 调用:`client.messages.parse(model=settings.anthropic_model, max_tokens=16000, thinking={"type": "adaptive"}, system=PLANNER_SYSTEM_PROMPT, messages=[...], output_format=PlanSpec)`
- `parsed_output` 为 None 时抛 `RuntimeError("LLM 输出解析失败")`

## 实现内容

### `backend/app/llm/planner.py`

```python
import anthropic

from ..config import settings
from .schema import PlanSpec

PLANNER_SYSTEM_PROMPT = """你是一个目标规划专家。用户给出一个目标，你要把它拆解成一份完整计划。

输出结构：
- strategy：一句话总体策略
- milestones：3-6 个阶段性小目标，按 order 排序；target_date_offset_days 为该里程碑相对计划开始日的天数偏移
- 每个 milestone 有 3-10 个 tasks，按学习顺序串行（先基础后进阶）

任务规则：
- 每个 task 有 type，取值 learn(学习)/practice(实操)/project(项目)
- effort_hours 为预估工时：学习 0.5-2，实操 1-4，项目 2-8
- 描述用中文，具体可执行"""


def generate_plan(
    goal_title: str,
    description: str,
    target_date: str | None,
    client: anthropic.Anthropic | None = None,
) -> PlanSpec:
    client = client or anthropic.Anthropic()
    user_prompt = f"目标：{goal_title}\n说明：{description or '无'}"
    if target_date:
        user_prompt += f"\n期望完成日期：{target_date}"
    user_prompt += "\n请生成完整计划。"
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=PLANNER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=PlanSpec,
    )
    if response.parsed_output is None:
        raise RuntimeError("LLM 输出解析失败")
    return response.parsed_output
```

### `backend/tests/test_planner.py`

```python
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
```

## 完成标准

1. 先写测试确认失败 → 再实现 → `cd backend && python -m pytest tests/test_planner.py -v` → `1 passed`
2. 创建 git commit(`feat: llm plan generation with structured output`)
3. 报告:提交 hash、测试摘要、concerns

## 注意

- 这是判断型任务,LLM 调用参数必须与计划完全一致(尤其 `output_format`、`thinking`、模型 ID)
- 不要在该任务里做任何日期计算(那是 Task 5 服务层的活)

## 提交命令

```bash
git add backend/app/llm/planner.py backend/tests/test_planner.py
git commit -m "feat: llm plan generation with structured output"
```

## 报告

<!-- Codex: 完成后在此填写 -->
