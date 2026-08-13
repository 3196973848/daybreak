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
