import json
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from ..config import settings
from .schema import PlanSpec

PLANNER_SYSTEM_PROMPT = """你是一个目标规划专家。请先自动识别目标涉及的知识领域，再把每个领域拆成具体子知识点对应的原子任务。

输出 JSON，严格遵循以下结构（每个字段都要有）：
{
  "strategy": "一句话总体策略",
  "milestones": [
    {
      "title": "知识领域标题",
      "description": "领域学习目标说明",
      "order": 1,
      "tasks": [
        {
          "title": "具体子知识点",
          "description": "可验证的具体学习成果",
          "type": "learn",
          "effort_hours": 0.5
        }
      ]
    }
  ]
}

规则：
- 自动识别完成目标所需的领域，按学习先后顺序设置 order
- 每个任务只覆盖一个具体子知识点，必须有非空 title 和 description
- type 取值 learn（学习）、practice（实操）或 project（项目）
- effort_hours 必须按 0.5 小时递增，且单个任务不能超过用户的每日预算
- 不要输出日期、截止日、日期偏移或任何排程字段；日期由排程器统一决定
- 描述使用中文，具体、可执行、成果可验证
- 只输出 JSON，不要输出任何其他文字或 markdown"""


def _client(client: OpenAI | None) -> OpenAI:
    if client is not None:
        return client
    return OpenAI(api_key=settings.llm_api_key or None, base_url=settings.llm_base_url)


def generate_plan(
    goal_title: str,
    description: str,
    target_date: str | None,
    daily_hours: float = 2.0,
    feedback: str | None = None,
    client: OpenAI | None = None,
) -> PlanSpec:
    c = _client(client)
    user_prompt = (
        f"目标：{goal_title}\n"
        f"说明：{description or '无'}\n"
        f"每日可投入时间：{daily_hours} 小时"
    )
    if target_date:
        user_prompt += f"\n期望完成日期（仅用于控制计划范围）：{target_date}"
    if feedback:
        user_prompt += f"\n上次计划校验失败：{feedback}\n请修正后重新生成完整计划。"
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
