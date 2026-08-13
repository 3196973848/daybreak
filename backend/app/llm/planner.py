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
