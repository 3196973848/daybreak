import json
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from ..config import settings
from .schema import PlanSpec

PLANNER_SYSTEM_PROMPT = """你是一个目标规划专家。用户给出一个目标，你要把它拆解成一份完整计划。

输出 JSON，严格遵循以下结构（每个字段都要有）：
{
  "strategy": "一句话总体策略",
  "milestones": [
    {
      "title": "里程碑标题",
      "description": "阶段目标说明",
      "order": 1,
      "target_date_offset_days": 14,
      "tasks": [
        {
          "title": "任务标题",
          "description": "具体可执行的任务内容",
          "type": "learn",
          "effort_hours": 1.0
        }
      ]
    }
  ]
}

规则：
- 3-6 个里程碑，按 order 排序，target_date_offset_days 为相对计划开始日的天数偏移
- 每个里程碑 3-10 个任务，按学习顺序串行
- type 取值 learn(学习)/practice(实操)/project(项目)；effort_hours 学习0.5-2、实操1-4、项目2-8
- 描述用中文，具体可执行
- 只输出 JSON，不要输出任何其它文字或 markdown"""


def _client(client: OpenAI | None) -> OpenAI:
    if client is not None:
        return client
    return OpenAI(api_key=settings.llm_api_key or None, base_url=settings.llm_base_url)


def generate_plan(
    goal_title: str,
    description: str,
    target_date: str | None,
    client: OpenAI | None = None,
) -> PlanSpec:
    c = _client(client)
    user_prompt = f"目标：{goal_title}\n说明：{description or '无'}"
    if target_date:
        user_prompt += f"\n期望完成日期：{target_date}"
    user_prompt += "\n请生成完整计划。"
    response = c.chat.completions.create(
        model=settings.llm_model,
        max_tokens=16000,
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("LLM 返回为空")
    return parse_plan_spec(text)


def parse_plan_spec(text: str) -> PlanSpec:
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM 输出不是合法 JSON") from exc
    try:
        return PlanSpec.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError("LLM 输出不符合结构") from exc
