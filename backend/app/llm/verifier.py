import json
from typing import Any, List

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from ..config import settings


class Question(BaseModel):
    id: int
    type: str  # choice | short
    text: str
    options: List[str] = []


class TestContent(BaseModel):
    questions: List[Question]


class DeliverContent(BaseModel):
    acceptance_criteria: str


class GradeResult(BaseModel):
    score: float
    feedback: str


TEST_GENERATE_PROMPT = """你是学习测试出题助手。基于学习任务内容生成 2-3 道选择题和 1 道简答题。
选择题必须含 4 个选项且仅一个正确；简答题 options 为空。只输出 JSON，不输出其它内容。
输出格式：{"questions": [{"id": 1, "type": "choice", "text": "...", "options": ["a","b","c","d"]}, {"id": 2, "type": "short", "text": "...", "options": []}]}"""

GRADE_TEST_PROMPT = """你是严格但公平的评分老师。依据学习任务内容与题目，判断用户答案正确率。
只输出 JSON：{"score": 0-1(正确率), "feedback": "中文评语"}。"""

DELIVER_GENERATE_PROMPT = """你是交付验收设计者。为实操/项目任务写 2-5 条明确、可检验的验收标准。
只输出 JSON：{"acceptance_criteria": "标准文本"}。"""

GRADE_DELIVER_PROMPT = """你是交付验收评审员。依据验收标准判断用户提交的成果描述是否达标。
只输出 JSON：{"score": 0-1(达标度), "feedback": "中文评审意见"}。score>=0.7 表示达标。"""


def _client(client: OpenAI | None) -> OpenAI:
    if client is not None:
        return client
    return OpenAI(api_key=settings.llm_api_key or None, base_url=settings.llm_base_url)


def _parse(client, system_prompt, user_prompt, output_model, max_tokens=4000):
    c = _client(client)
    response = c.chat.completions.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content
    if not text:
        raise RuntimeError("LLM 返回为空")
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM 输出不是合法 JSON") from exc
    try:
        return output_model.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError("LLM 输出不符合结构") from exc


def generate_test(task_title: str, task_description: str, client=None) -> TestContent:
    return _parse(
        client, TEST_GENERATE_PROMPT,
        f"任务：{task_title}\n内容：{task_description or '无'}",
        TestContent,
    )


def grade_test(
    task_title: str, task_description: str, content: TestContent, answers: dict, client=None
) -> GradeResult:
    payload = {
        "任务": task_title,
        "内容": task_description or "无",
        "题目": [q.model_dump() for q in content.questions],
        "用户答案": answers,
    }
    return _parse(
        client, GRADE_TEST_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        GradeResult,
    )


def generate_deliver_criteria(task_title: str, task_description: str, client=None) -> DeliverContent:
    return _parse(
        client, DELIVER_GENERATE_PROMPT,
        f"任务：{task_title}\n内容：{task_description or '无'}",
        DeliverContent,
    )


def grade_delivery(
    task_title: str, task_description: str, criteria: str, submission: str, client=None
) -> GradeResult:
    payload = {
        "任务": task_title,
        "内容": task_description or "无",
        "验收标准": criteria,
        "用户提交": submission,
    }
    return _parse(
        client, GRADE_DELIVER_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        GradeResult,
    )
