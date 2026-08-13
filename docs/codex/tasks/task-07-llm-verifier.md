# Task 7: LLM 检验模块(测试 / 交付)

## 目标

实现检验模块四个函数:出题、判分(测试模式)+ 出验收标准、评审(交付模式),用 fake client 单测。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 7** 一节。

## 要创建的文件

- `backend/app/llm/verifier.py`
- `backend/tests/test_verifier.py`

## 关键接口(后续 Task 8 依赖,必须一致)

```python
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

def generate_test(task_title, task_description, client=None) -> TestContent
def grade_test(task_title, task_description, content: TestContent, answers: dict, client=None) -> GradeResult
def generate_deliver_criteria(task_title, task_description, client=None) -> DeliverContent
def grade_delivery(task_title, task_description, criteria: str, submission: str, client=None) -> GradeResult
```

- 所有函数 `client=None`,内部 `client = client or anthropic.Anthropic()`
- 统一走 `_parse(client, system_prompt, user_prompt, output_model, max_tokens=4000)` helper,`client.messages.parse(..., output_format=output_model)`,模型 `settings.anthropic_model`,`thinking={"type": "adaptive"}`
- `parsed_output` None 时抛 `RuntimeError("LLM 输出解析失败")`

## 实现内容

### `backend/app/llm/verifier.py`

```python
import json
from typing import List

import anthropic
from pydantic import BaseModel

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
选择题必须含 4 个选项且仅一个正确；简答题 options 为空。只输出 JSON，不输出其它内容。"""

GRADE_TEST_PROMPT = """你是严格但公平的评分老师。依据学习任务内容与题目，判断用户答案正确率。
返回 JSON：{"score": 0-1(正确率), "feedback": "中文评语"}。"""

DELIVER_GENERATE_PROMPT = """你是交付验收设计者。为实操/项目任务写 2-5 条明确、可检验的验收标准。
只输出 JSON：{"acceptance_criteria": "标准文本"}。"""

GRADE_DELIVER_PROMPT = """你是交付验收评审员。依据验收标准判断用户提交的成果描述是否达标。
返回 JSON：{"score": 0-1(达标度), "feedback": "中文评审意见"}。score>=0.7 表示达标。"""


def _parse(client, system_prompt, user_prompt, output_model, max_tokens=4000):
    client = client or anthropic.Anthropic()
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=output_model,
    )
    if response.parsed_output is None:
        raise RuntimeError("LLM 输出解析失败")
    return response.parsed_output


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
```

### `backend/tests/test_verifier.py`

```python
from app.llm.verifier import (
    DeliverContent,
    GradeResult,
    TestContent,
    generate_deliver_criteria,
    generate_test,
    grade_delivery,
    grade_test,
)
from app.llm.schema import PlanSpec  # noqa: F401  (ensure schema import works)


class FakeResponse:
    def __init__(self, parsed):
        self.parsed_output = parsed


class FakeMessages:
    def __init__(self, value):
        self._value = value

    def parse(self, **kwargs):
        return FakeResponse(self._value)


class FakeClient:
    def __init__(self, value):
        self.messages = FakeMessages(value)


def test_generate_test():
    content = TestContent(questions=[
        {"id": 1, "type": "choice", "text": "哪个是变量名?", "options": ["a", "b"]},
        {"id": 2, "type": "short", "text": "什么是赋值?", "options": []},
    ])
    got = generate_test("任务", "内容", client=FakeClient(content))
    assert got.questions[0].type == "choice"


def test_grade_test_passed_threshold():
    grade = GradeResult(score=0.9, feedback="很好")
    got = grade_test("任务", "内容", TestContent(questions=[]), {"1": "a"}, client=FakeClient(grade))
    assert got.score >= 0.7


def test_generate_deliver_criteria():
    got = generate_deliver_criteria("写计算器", "支持四则运算", client=FakeClient(DeliverContent(acceptance_criteria="支持加减乘除")))
    assert got.acceptance_criteria == "支持加减乘除"


def test_grade_delivery():
    grade = GradeResult(score=0.5, feedback="不达标")
    got = grade_delivery("写计算器", "内容", "标准", "我的成果", client=FakeClient(grade))
    assert got.score < 0.7
```

## 完成标准

1. 先写测试确认失败 → 再实现 → `cd backend && python -m pytest tests/test_verifier.py -v` → `4 passed`
2. 创建 git commit(`feat: llm verification module for test and deliver modes`)
3. 报告:提交 hash、测试摘要、concerns

## 注意

- 这是判断型任务,LLM 参数必须与计划一致
- `passed` 判定**不在本模块**,由 Task 8 API 层按 `score >= 0.7` 计算

## 提交命令

```bash
git add backend/app/llm/verifier.py backend/tests/test_verifier.py
git commit -m "feat: llm verification module for test and deliver modes"
```

## 报告

<!-- Codex: 完成后在此填写 -->
