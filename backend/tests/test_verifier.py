import json

import pytest
from pydantic import ValidationError

from app.llm.verifier import (
    DeliverContent,
    GradeResult,
    ShortGradeResult,
    TestContent,
    generate_deliver_criteria,
    generate_test,
    grade_delivery,
    grade_short_answers,
    score_test,
)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return type("Resp", (), {"choices": [FakeChoice(self._content)]})()


class FakeClient:
    def __init__(self, value):
        self.chat = type("Chat", (), {"completions": FakeCompletions(value.model_dump_json())})()


def quiz_payload(prefix="题"):
    questions = [
        {
            "id": i,
            "type": "choice",
            "text": f"{prefix}{i}",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "reference_answer": None,
            "rubric_points": [],
        }
        for i in range(1, 8)
    ]
    questions.extend(
        {
            "id": i,
            "type": "short",
            "text": f"{prefix}{i}",
            "options": [],
            "correct_answer": None,
            "reference_answer": f"参考{i}",
            "rubric_points": ["要点一", "要点二"],
        }
        for i in range(8, 11)
    )
    return {"questions": questions}


class SequentialCompletions:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps(self.payloads.pop(0), ensure_ascii=False)
        return type("Resp", (), {"choices": [FakeChoice(content)]})()


class SequentialClient:
    def __init__(self, payloads):
        self.completions = SequentialCompletions(payloads)
        self.chat = type("Chat", (), {"completions": self.completions})()


def test_generate_test_requires_seven_choice_then_three_short_questions():
    client = SequentialClient([quiz_payload()])
    content = generate_test("任务", "内容", client=client)
    assert len(content.questions) == 10
    assert [q.type for q in content.questions] == ["choice"] * 7 + ["short"] * 3
    assert [q.id for q in content.questions] == list(range(1, 11))


def test_public_quiz_does_not_expose_answers_or_rubrics():
    content = TestContent.model_validate(quiz_payload())
    public = content.public_dump()
    encoded = json.dumps(public, ensure_ascii=False)
    assert "correct_answer" not in encoded
    assert "reference_answer" not in encoded
    assert "rubric_points" not in encoded
    assert len(public["questions"]) == 10


def test_generate_test_retries_invalid_shape_and_duplicate_history():
    invalid = quiz_payload("无效")
    invalid["questions"] = invalid["questions"][:9]
    duplicate = quiz_payload("旧题")
    fresh = quiz_payload("新题")
    client = SequentialClient([invalid, duplicate, fresh])
    result = generate_test(
        "任务", "内容", previous_question_texts=[f"旧题{i}" for i in range(1, 11)], client=client
    )
    assert result.questions[0].text == "新题1"
    assert len(client.completions.calls) == 3


def test_generate_test_fails_after_three_invalid_attempts():
    invalid = {"questions": []}
    client = SequentialClient([invalid, invalid, invalid])
    with pytest.raises(RuntimeError, match="生成 10 道检验题失败"):
        generate_test("任务", "内容", client=client)


def test_test_content_rejects_invalid_private_question_fields():
    payload = quiz_payload()
    payload["questions"][0]["correct_answer"] = "Z"
    with pytest.raises(ValidationError):
        TestContent.model_validate(payload)


def test_score_test_combines_seven_exact_choices_and_three_short_scores():
    content = TestContent.model_validate(quiz_payload())
    answers = {str(i): "A" for i in range(1, 8)} | {"8": "answer", "9": "answer", "10": "answer"}
    short = ShortGradeResult(items=[
        {"id": 8, "score": 10, "feedback": "complete"},
        {"id": 9, "score": 5, "feedback": "partly correct"},
        {"id": 10, "score": 0, "feedback": "not answered"},
    ])
    result = score_test(content, answers, short)
    assert result.points == 85
    assert result.score == 0.85
    assert result.details[0].correct is True
    assert result.details[0].correct_answer == "A"
    assert result.details[7].points == 10


def test_score_test_gives_zero_for_missing_or_wrong_choice_answers():
    content = TestContent.model_validate(quiz_payload())
    short = ShortGradeResult(items=[
        {"id": 8, "score": 0, "feedback": ""},
        {"id": 9, "score": 0, "feedback": ""},
        {"id": 10, "score": 0, "feedback": ""},
    ])
    result = score_test(content, {"1": "B"}, short)
    assert result.points == 0
    assert result.details[0].correct is False
    assert result.details[1].points == 0


def test_short_grade_requires_exact_short_question_ids():
    with pytest.raises(ValidationError):
        ShortGradeResult(items=[{"id": 8, "score": 10, "feedback": "x"}])


def test_short_grade_rejects_scores_outside_zero_to_ten():
    with pytest.raises(ValidationError):
        ShortGradeResult(items=[
            {"id": 8, "score": 11, "feedback": "x"},
            {"id": 9, "score": 0, "feedback": "x"},
            {"id": 10, "score": 0, "feedback": "x"},
        ])


def test_grade_short_answers_sends_only_short_questions_to_llm():
    grade = ShortGradeResult(items=[
        {"id": 8, "score": 10, "feedback": "x"},
        {"id": 9, "score": 5, "feedback": "y"},
        {"id": 10, "score": 0, "feedback": "z"},
    ])
    client = SequentialClient([grade.model_dump()])
    got = grade_short_answers(
        "task", "description", TestContent.model_validate(quiz_payload()),
        {"1": "B", "8": "short 8", "9": "short 9", "10": "short 10"}, client=client,
    )
    user_prompt = client.completions.calls[0]["messages"][1]["content"]
    short_questions = json.loads(user_prompt)["简答题"]
    assert [item.id for item in got.items] == [8, 9, 10]
    assert [item["id"] for item in short_questions] == [8, 9, 10]
    assert [item["user_answer"] for item in short_questions] == ["short 8", "short 9", "short 10"]


def test_grade_short_answers_fails_after_three_invalid_results():
    invalid = {"items": [{"id": 8, "score": 10, "feedback": "x"}]}
    client = SequentialClient([invalid, invalid, invalid])
    with pytest.raises(RuntimeError):
        grade_short_answers(
            "task", "description", TestContent.model_validate(quiz_payload()), {}, client=client
        )
    assert len(client.completions.calls) == 3


def test_generate_deliver_criteria():
    got = generate_deliver_criteria("写计算器", "支持四则运算", client=FakeClient(DeliverContent(acceptance_criteria="支持加减乘除")))
    assert got.acceptance_criteria == "支持加减乘除"


def test_grade_delivery():
    grade = GradeResult(score=0.5, feedback="不达标")
    got = grade_delivery("写计算器", "内容", "标准", "我的成果", client=FakeClient(grade))
    assert got.score < 0.7
