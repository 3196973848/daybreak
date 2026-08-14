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


class ShortQuestionGrade(BaseModel):
    id: int
    score: float = Field(ge=0, le=10)
    feedback: str


class ShortGradeResult(BaseModel):
    items: list[ShortQuestionGrade]

    @model_validator(mode="after")
    def validate_ids(self):
        if [item.id for item in self.items] != [8, 9, 10]:
            raise ValueError("简答评分必须依次包含题目 8、9、10")
        return self


class _AnsweredShortGradeResult(BaseModel):
    items: list[ShortQuestionGrade]


class QuizQuestionResult(BaseModel):
    id: int
    type: Literal["choice", "short"]
    points: float
    correct: bool | None = None
    correct_answer: str | None = None
    feedback: str = ""


class QuizScore(BaseModel):
    points: float
    score: float
    feedback: str
    details: list[QuizQuestionResult]


TEST_GENERATE_PROMPT = """你是学习测试出题助手。基于学习任务内容生成恰好 10 道检验题：前 7 道为选择题，后 3 道为简答题。
只输出 JSON，不输出其它内容。选择题必须包含 id、type="choice"、text、恰好 4 个 options、且 correct_answer 必须是 options 之一；reference_answer 必须为 null，rubric_points 必须为 []。简答题必须包含 id、type="short"、text、options=[]、correct_answer=null、非空 reference_answer、以及非空 rubric_points。题目 id 必须依次为 1 到 10。
输出格式：{"questions": [{"id": 1, "type": "choice", "text": "...", "options": ["a", "b", "c", "d"], "correct_answer": "a", "reference_answer": null, "rubric_points": []}, {"id": 8, "type": "short", "text": "...", "options": [], "correct_answer": null, "reference_answer": "...", "rubric_points": ["..."]}]}"""

SHORT_GRADE_PROMPT = """你是严格但公平的简答题评分老师。只根据每道题的参考答案和评分点评分。
必须只输出 JSON，items 必须依次且恰好包含输入中提供的题目 ID，不得添加或遗漏；每题 score 必须在 0 到 10 之间，并给出 feedback。输出格式：{"items": [{"id": 8, "score": 0, "feedback": "中文评语"}]}"""

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


def grade_short_answers(
    task_title: str,
    task_description: str,
    content: TestContent,
    answers: dict[str, str],
    client=None,
) -> ShortGradeResult:
    short_questions = [
        {
            "id": q.id,
            "text": q.text,
            "reference_answer": q.reference_answer,
            "rubric_points": q.rubric_points,
            "user_answer": answers.get(str(q.id), ""),
        }
        for q in content.questions
        if q.type == "short"
        and isinstance(answers.get(str(q.id)), str)
        and bool(answers[str(q.id)].strip())
    ]
    answered_ids = [question["id"] for question in short_questions]
    if not answered_ids:
        return ShortGradeResult(items=[
            ShortQuestionGrade(id=q.id, score=0, feedback="")
            for q in content.questions
            if q.type == "short"
        ])
    errors = []
    for _attempt in range(3):
        try:
            answered_grade = _parse(
                client,
                SHORT_GRADE_PROMPT,
                json.dumps(
                    {"任务": task_title, "内容": task_description, "简答题": short_questions},
                    ensure_ascii=False,
                ),
                _AnsweredShortGradeResult,
            )
            if [item.id for item in answered_grade.items] != answered_ids:
                raise RuntimeError("LLM 输出的简答题编号与已作答题目不一致")
            answered_by_id = {item.id: item for item in answered_grade.items}
            return ShortGradeResult(items=[
                answered_by_id.get(q.id)
                or ShortQuestionGrade(id=q.id, score=0, feedback="")
                for q in content.questions
                if q.type == "short"
            ])
        except RuntimeError as exc:
            errors.append(str(exc))
    raise RuntimeError(f"简答题评分失败：{'；'.join(errors)}")


def score_test(
    content: TestContent,
    answers: dict[str, str],
    short_grade: ShortGradeResult,
) -> QuizScore:
    short_by_id = {item.id: item for item in short_grade.items}
    details = []
    for question in content.questions:
        if question.type == "choice":
            correct = answers.get(str(question.id)) == question.correct_answer
            details.append(
                QuizQuestionResult(
                    id=question.id,
                    type="choice",
                    points=10 if correct else 0,
                    correct=correct,
                    correct_answer=question.correct_answer,
                )
            )
        else:
            answer = answers.get(str(question.id))
            answered = isinstance(answer, str) and bool(answer.strip())
            grade = short_by_id[question.id]
            details.append(
                QuizQuestionResult(
                    id=question.id,
                    type="short",
                    points=grade.score if answered else 0,
                    feedback=grade.feedback if answered else "",
                )
            )
    points = round(sum(item.points for item in details), 1)
    feedback = "\n".join(item.feedback for item in details if item.feedback)
    return QuizScore(points=points, score=points / 100, feedback=feedback, details=details)


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
