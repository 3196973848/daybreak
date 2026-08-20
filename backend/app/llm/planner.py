import json
from typing import Any

from pydantic import ValidationError

from ..config import settings
from .client import chat
from .schema import PlanSpec, PreviewSpec

PLANNER_SYSTEM_PROMPT = """你是一个目标规划专家。请先自动识别目标涉及的知识领域，再把每个领域拆成具体子知识点对应的原子任务。

输出 JSON，严格遵循以下结构（每个字段都要有）：
{
  "strategy": "一句话总体策略",
  "assumptions": ["假设1：...", "假设2：...", "假设3：..."],
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

- assumptions 列出 3-5 条你在制定计划时做的关键假设（如用户已有知识、可用时间、资源等）
- 自动识别完成目标所需的领域，按学习先后顺序设置 order
- 每个任务只覆盖一个具体子知识点，必须有非空 title 和 description
- type 取值 learn（学习）、practice（实操）或 project（项目）
- effort_hours 必须按 0.5 小时递增，且单个任务不能超过用户的每日预算
- 不要输出日期、截止日、日期偏移或任何排程字段；日期由排程器统一决定
- 描述使用中文，具体、可执行、成果可验证
- 只输出 JSON，不要输出任何其他文字或 markdown"""


def generate_plan(
    goal_title: str,
    description: str,
    target_date: str | None,
    daily_hours: float = 2.0,
    feedback: str | None = None,
    rejected_assumptions: list[str] | None = None,
    client=None,
) -> PlanSpec:
    user_prompt = (
        f"目标：{goal_title}\n"
        f"说明：{description or '无'}\n"
        f"每日可投入时间：{daily_hours} 小时"
    )
    if target_date:
        user_prompt += f"\n期望完成日期（仅用于控制计划范围）：{target_date}"
    if rejected_assumptions:
        user_prompt += "\n\n用户否决了以下假设，请调整计划：\n" + "\n".join(f"- {a}" for a in rejected_assumptions)
    if feedback:
        user_prompt += f"\n上次计划校验失败：{feedback}\n请修正后重新生成完整计划。"
    user_prompt += "\n请生成完整计划。"
    text = chat(
        [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=settings.llm_model,
        max_tokens=16000,
        client=client,
    )
    if not text:
        raise RuntimeError("LLM 返回为空")
    return parse_plan_spec(text)


def generate_preview(
    goal_title: str,
    description: str,
    target_date: str | None,
    daily_hours: float = 2.0,
    client=None,
) -> PreviewSpec:
    user_prompt = (
        f"目标：{goal_title}\n"
        f"说明：{description or '无'}\n"
        f"每日可投入时间：{daily_hours} 小时"
    )
    if target_date:
        user_prompt += f"\n期望完成日期：{target_date}"
    user_prompt += "\n请生成计划预览（里程碑大纲和关键假设）。"
    text = chat(
        [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=settings.llm_model,
        max_tokens=8000,
        client=client,
    )
    if not text:
        raise RuntimeError("LLM 返回为空")
    return parse_preview_spec(text)


def parse_plan_spec(text: str) -> PlanSpec:
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM 输出不是合法 JSON") from exc
    try:
        return PlanSpec.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError("LLM 输出不符合结构") from exc


def parse_preview_spec(text: str) -> PreviewSpec:
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM 输出不是合法 JSON") from exc
    try:
        return PreviewSpec.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError("LLM 输出不符合结构") from exc
