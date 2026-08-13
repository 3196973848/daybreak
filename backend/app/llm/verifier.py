import json
from typing import Any, Literal
from uuid import uuid4

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, model_validator

from ..config import settings


class Question(BaseModel):
    id: int
    type: Literal["choice", "short"]
    text: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    correct_answer: str | None = None
    reference_answer: str | None = None
    rubric_points: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_private_answer(self):
        if self.type == "choice":
            if len(self.options) != 4 or self.correct_answer not in self.options:
                raise ValueError("选择题必须有四个选项且正确答案属于选项")
            if self.reference_answer is not None or self.rubric_points:
                raise ValueError("选择题不能包含简答题评分字段")
        else:
            if self.options or self.correct_answer is not None:
                raise ValueError("简答题不能包含选项或选择题答案")
            if not self.reference_answer or not self.rubric_points:
                raise ValueError("简答题必须包含参考答案和评分点")
        return self

    def public_dump(self) -> dict[str, object]:
        return {"id": self.id, "type": self.type, "text": self.text, "options": self.options}


class TestContent(BaseModel):
    questions: list[Question]

    @model_validator(mode="after")
    def validate_quiz_shape(self):
        if len(self.questions) != 10:
            raise ValueError("检验题必须恰好为 10 道")
        if [q.id for q in self.questions] != list(range(1, 11)):
            raise ValueError("检验题号必须为 1 到 10")
        if [q.type for q in self.questions] != ["choice"] * 7 + ["short"] * 3:
            raise ValueError("检验题必须为前 7 道选择题和后 3 道简答题")
        return self

    def public_dump(self) -> dict[str, object]:
        return {"questions": [question.public_dump() for question in self.questions]}


class DeliverContent(BaseModel):
    acceptance_criteria: str


class GradeResult(BaseModel):
    score: float
    feedback: str


TEST_GENERATE_PROMPT = """你是学习测试出题助手。基于学习任务内容生成恰好 10 道检验题：前 7 道为选择题，后 3 道为简答题。
只输出 JSON，不输出其它内容。选择题必须包含 id、type="choice"、text、恰好 4 个 options、且 correct_answer 必须是 options 之一；reference_answer 必须为 null，rubric_points 必须为 []。简答题必须包含 id、type="short"、text、options=[]、correct_answer=null、非空 reference_answer、以及非空 rubric_points。题目 id 必须依次为 1 到 10。
输出格式：{"questions": [{"id": 1, "type": "choice", "text": "...", "options": ["a", "b", "c", "d"], "correct_answer": "a", "reference_answer": null, "rubric_points": []}, {"id": 8, "type": "short", "text": "...", "options": [], "correct_answer": null, "reference_answer": "...", "rubric_points": ["..."]}]}"""

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


def _normalize_question(text: str) -> str:
    return " ".join(text.casefold().split())


def generate_test(
    task_title: str,
    task_description: str,
    previous_question_texts: list[str] | None = None,
    client=None,
) -> TestContent:
    previous = {_normalize_question(text) for text in previous_question_texts or []}
    errors = []
    for _attempt in range(3):
        request_id = str(uuid4())
        user_prompt = (
            f"任务：{task_title}\n内容：{task_description or '无'}\n"
            f"本次请求标识：{request_id}\n"
            f"不得重复的历史题干：{json.dumps(sorted(previous), ensure_ascii=False)}"
        )
        try:
            content = _parse(client, TEST_GENERATE_PROMPT, user_prompt, TestContent, max_tokens=8000)
            current = {_normalize_question(question.text) for question in content.questions}
            if current & previous:
                raise RuntimeError("题干与历史检验重复")
            return content
        except RuntimeError as exc:
            errors.append(str(exc))
    raise RuntimeError(f"生成 10 道检验题失败：{'；'.join(errors)}")


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
