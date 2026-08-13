# Transparent Verification and Adaptive Daily Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build ten-question learning verification with transparent scoring and loading feedback, plus model-driven atomic task decomposition scheduled by a user-configurable daily time budget.

**Architecture:** Keep the two workflows independent at their service boundaries. Verification stores a private quiz model in `VerificationRecord`, returns a sanitized public model, scores choices deterministically, and asks DeepSeek only for per-question short-answer scores. Planning asks DeepSeek for domain milestones and atomic half-hour tasks, validates them, groups them by daily capacity, and uniformly maps those groups across the inclusive natural-day range.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, OpenAI-compatible DeepSeek client, pytest, React 18, TypeScript, Vitest, Testing Library, Vite. Do not add LangGraph or any new dependency.

## Global Constraints

- DeepSeek remains at `https://api.deepseek.com` using `settings.llm_model`; do not introduce Anthropic or OpenAI-hosted endpoints.
- Never log, commit, return, or render the DeepSeek API key.
- Learning verification contains exactly 7 choice questions followed by 3 short-answer questions.
- Each quiz question is worth 10 points; a backend-computed total of at least 70 points passes.
- Private choice answers, short reference answers, and rubrics must not appear in the verification-start response.
- Each verification request carries a fresh request ID and rejects exact normalized question-text reuse for the same task.
- `daily_hours` defaults to `2.0`, must be finite, positive, and a multiple of `0.5`.
- Each atomic task is at least `0.5` hours, a multiple of `0.5`, and no longer than `daily_hours`.
- Scheduling includes weekends, preserves task order, never exceeds the daily time budget, and uniformly spans today through the inclusive deadline.
- Capacity failure creates no Goal and returns `required_hours`, `available_hours`, `minimum_days`, and `suggested_duration`.
- The LLM chooses domains, atomic content, order, type, and effort only; it never chooses dates.
- Use TDD for every production-code change. Capture a relevant RED before the minimal GREEN implementation.

---

### Task 1: Private Ten-Question Quiz Generation and Deduplication

**Files:**
- Modify: `backend/app/llm/verifier.py`
- Modify: `backend/tests/test_verifier.py`

**Interfaces:**
- Produces: `TestContent` with exactly ten private `Question` objects.
- Produces: `TestContent.public_dump() -> dict[str, object]`, which excludes all answer and rubric fields.
- Produces: `generate_test(task_title: str, task_description: str, previous_question_texts: list[str] | None = None, client=None) -> TestContent`.
- Preserves: `DeliverContent`, `GradeResult`, `generate_deliver_criteria()`, and `grade_delivery()`.

- [ ] **Step 1: Replace the loose quiz fixture with failing structure and secrecy tests**

Add `pytest`, a sequential fake client, and helpers to `backend/tests/test_verifier.py`:

```python
import json
import pytest
from pydantic import ValidationError


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
```

Add these tests:

```python
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
```

- [ ] **Step 2: Run the focused verifier tests and verify RED**

Run:

```powershell
Set-Location backend
D:\conda\envs\dl2025\python.exe -m pytest tests/test_verifier.py -v
```

Expected: failures because the current model accepts arbitrary counts, has no private answer fields, has no `public_dump()`, and does not retry or deduplicate.

- [ ] **Step 3: Implement strict private/public quiz models**

In `backend/app/llm/verifier.py`, use `Literal`, `Field`, and `model_validator` to define:

```python
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
```

- [ ] **Step 4: Implement bounded generation retries and exact normalized deduplication**

Replace the generation prompt with an exact JSON contract for 7 choice plus 3 short questions. Add:

```python
def _normalize_question(text: str) -> str:
    return " ".join(text.casefold().split())


def generate_test(task_title, task_description, previous_question_texts=None, client=None):
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
```

Import `uuid4`. Reuse `_parse()`; do not add a workflow framework.

- [ ] **Step 5: Run verifier tests and full backend tests**

Run:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_verifier.py -v
D:\conda\envs\dl2025\python.exe -m pytest
```

Expected: the focused tests pass. Update existing loose two-question fixtures in backend tests to use the ten-question helper so the full suite also passes.

- [ ] **Step 6: Commit Task 1**

```powershell
git add backend/app/llm/verifier.py backend/tests/test_verifier.py backend/tests/test_tasks_api.py
git commit -m "feat: generate private ten-question quizzes"
```

---

### Task 2: Deterministic Choice Scoring and Rubric-Based Short Scoring

**Files:**
- Modify: `backend/app/llm/verifier.py`
- Modify: `backend/app/api/tasks.py`
- Modify: `backend/tests/test_verifier.py`
- Modify: `backend/tests/test_tasks_api.py`

**Interfaces:**
- Produces: `ShortQuestionGrade(id: int, score: float, feedback: str)` with score constrained to `0..10`.
- Produces: `ShortGradeResult(items: list[ShortQuestionGrade])` containing exactly question IDs 8, 9, and 10.
- Produces: `grade_short_answers(...) -> ShortGradeResult`.
- Produces: `score_test(content: TestContent, answers: dict[str, str], short_grade: ShortGradeResult) -> QuizScore`.
- API response keeps `score` in `0..1` and adds `points` plus `details`.

- [ ] **Step 1: Add failing deterministic-scoring tests**

Add to `backend/tests/test_verifier.py`:

```python
def test_score_test_combines_seven_exact_choices_and_three_short_scores():
    content = TestContent.model_validate(quiz_payload())
    answers = {str(i): "A" for i in range(1, 8)} | {"8": "答8", "9": "答9", "10": "答10"}
    short = ShortGradeResult(items=[
        {"id": 8, "score": 10, "feedback": "完整"},
        {"id": 9, "score": 5, "feedback": "部分正确"},
        {"id": 10, "score": 0, "feedback": "未命中"},
    ])
    result = score_test(content, answers, short)
    assert result.points == 85
    assert result.score == 0.85
    assert result.details[0].correct is True
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
```

Add an API boundary test to `backend/tests/test_tasks_api.py` that produces six correct choices and three zero-point short answers, submits, and asserts `points == 60`, `score == 0.6`, `passed is False`, and `task.verified is False`. Add another at exactly 70 points and assert it passes.

- [ ] **Step 2: Run focused scoring tests and verify RED**

```powershell
Set-Location backend
D:\conda\envs\dl2025\python.exe -m pytest tests/test_verifier.py tests/test_tasks_api.py -v
```

Expected: collection or assertion failures because short-grade and deterministic score types do not exist and the API delegates the entire grade to DeepSeek.

- [ ] **Step 3: Add score models and deterministic aggregation**

Implement models in `backend/app/llm/verifier.py`:

```python
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
```

Add `score_test()` that iterates the private questions in order. Choice answers are exact matches and return the correct answer after submission. Short points and feedback come from the validated grade map. Clamp no values in aggregation because Pydantic has already rejected out-of-range model output. Compute `points = round(sum(...), 1)` and `score = points / 100`.

- [ ] **Step 4: Ask DeepSeek only for the three short-answer scores with bounded retry**

Replace `grade_test()` with:

```python
def grade_short_answers(task_title, task_description, content, answers, client=None):
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
    ]
    errors = []
    for _attempt in range(3):
        try:
            return _parse(
                client,
                SHORT_GRADE_PROMPT,
                json.dumps({"任务": task_title, "内容": task_description, "简答题": short_questions}, ensure_ascii=False),
                ShortGradeResult,
            )
        except RuntimeError as exc:
            errors.append(str(exc))
    raise RuntimeError(f"简答题评分失败：{'；'.join(errors)}")
```

The system prompt must require one item for IDs 8, 9, and 10, each with a `0..10` score based only on its reference answer and rubric.

- [ ] **Step 5: Update the verification API transaction and public/private boundary**

In `start_verification()`, collect historical test question texts by parsing the task's prior `VerificationRecord.content`; call `generate_test(..., previous_question_texts=history)`; store `content.model_dump_json()` but return `content.public_dump()`.

Wrap generation and record creation in `try/except`; on failure call `db.rollback()` and raise `HTTPException(502, detail=f"检验题生成失败：{exc}")`.

In `submit_verification()`, replace the old full-quiz model grade with:

```python
short_grade = grade_short_answers(task.title, task.description, content, payload.answers)
quiz_score = score_test(content, payload.answers, short_grade)
grade_score = quiz_score.score
record.result = quiz_score.model_dump_json()
record.submission = json.dumps(payload.answers, ensure_ascii=False)
```

Keep delivery grading unchanged. Compute `passed = grade_score >= PASS_THRESHOLD` in the API. Return quiz `points` and `details` only for test mode; retain `passed`, `score`, `feedback`, and `verified` for both modes. On grading failure, rollback and return 502 without marking the task verified.

- [ ] **Step 6: Run focused and full backend tests**

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_verifier.py tests/test_tasks_api.py -v
D:\conda\envs\dl2025\python.exe -m pytest
```

Expected: all pass, including the exact 70-point boundary and the assertion that start responses contain no private answer fields.

- [ ] **Step 7: Commit Task 2**

```powershell
git add backend/app/llm/verifier.py backend/app/api/tasks.py backend/tests/test_verifier.py backend/tests/test_tasks_api.py
git commit -m "feat: score quizzes transparently"
```

---

### Task 3: Atomic Plan Generation and Daily-Capacity Scheduling

**Files:**
- Modify: `backend/app/llm/schema.py`
- Modify: `backend/app/llm/planner.py`
- Create: `backend/app/services/plan_validation.py`
- Modify: `backend/app/scheduler/scheduler.py`
- Modify: `backend/tests/test_planner.py`
- Create: `backend/tests/test_plan_validation.py`
- Modify: `backend/tests/test_scheduler.py`

**Interfaces:**
- `TaskSpec.effort_hours` remains a float; validation service enforces half-hour granularity relative to `daily_hours`.
- Removes model-owned `MilestoneSpec.target_date_offset_days`; dates are scheduler-owned.
- Produces: `validate_atomic_plan(plan: PlanSpec, daily_hours: float) -> None` raising `PlanValidationError`.
- Produces: `group_tasks(plan: PlanSpec, daily_hours: float) -> list[list[tuple[int, int]]]`.
- Extends: `schedule(..., end_date: date | None = None, daily_hours: float | None = None)`.
- Extends: `generate_plan(goal_title: str, description: str, target_date: str | None, daily_hours: float = 2.0, feedback: str | None = None, client: OpenAI | None = None) -> PlanSpec`.

- [ ] **Step 1: Add failing prompt and atomic-plan validation tests**

In `backend/tests/test_planner.py`, make the fake completions retain call kwargs and assert the user/system messages include the daily budget, autonomous domain identification, atomic subknowledge, half-hour increments, and prohibition on dates:

```python
generate_plan("学习交易", "", "2026-09-11", daily_hours=2.5, client=client)
prompt = json.dumps(client.completions.calls[0]["messages"], ensure_ascii=False)
assert "2.5" in prompt
assert "自行识别" in prompt
assert "具体子知识点" in prompt
assert "0.5" in prompt
assert "不要输出日期" in prompt
```

Create `backend/tests/test_plan_validation.py`:

```python
import pytest
from app.llm.schema import MilestoneSpec, PlanSpec, TaskSpec
from app.services.plan_validation import PlanValidationError, validate_atomic_plan


def plan_with(*efforts):
    return PlanSpec(
        strategy="策略",
        milestones=[MilestoneSpec(
            title="交易规则领域",
            order=1,
            tasks=[TaskSpec(title=f"知识点{i}", description="明确成果", effort_hours=e) for i, e in enumerate(efforts)],
        )],
    )


def test_atomic_plan_accepts_half_hour_tasks_within_daily_budget():
    validate_atomic_plan(plan_with(0.5, 1.0, 2.0), daily_hours=2.0)


@pytest.mark.parametrize("effort", [0, -0.5, 0.75, 2.5])
def test_atomic_plan_rejects_invalid_effort_or_task_over_budget(effort):
    with pytest.raises(PlanValidationError):
        validate_atomic_plan(plan_with(effort), daily_hours=2.0)
```

- [ ] **Step 2: Run planner/validation tests and verify RED**

```powershell
Set-Location backend
D:\conda\envs\dl2025\python.exe -m pytest tests/test_planner.py tests/test_plan_validation.py -v
```

Expected: missing module/signature failures and prompt assertions fail.

- [ ] **Step 3: Remove LLM-owned milestone offsets and implement validation**

Remove `target_date_offset_days` from `MilestoneSpec`. Update all backend test fixtures accordingly. Create:

```python
class PlanValidationError(ValueError):
    pass


def validate_atomic_plan(plan: PlanSpec, daily_hours: float) -> None:
    if not plan.milestones:
        raise PlanValidationError("计划必须包含至少一个领域")
    for milestone in plan.milestones:
        if not milestone.title.strip() or not milestone.tasks:
            raise PlanValidationError("每个领域必须有标题和原子任务")
        for task in milestone.tasks:
            if not task.title.strip() or not task.description.strip():
                raise PlanValidationError("原子任务必须有具体标题和成果描述")
            effort = task.effort_hours
            if not math.isfinite(effort) or effort < 0.5 or effort > daily_hours:
                raise PlanValidationError("任务耗时必须在 0.5 小时与每日预算之间")
            if not math.isclose(effort * 2, round(effort * 2)):
                raise PlanValidationError("任务耗时必须以 0.5 小时递增")
```

- [ ] **Step 4: Update the DeepSeek planning contract**

Extend `generate_plan()` with `daily_hours: float = 2.0` and `feedback: str | None = None`, keeping `client` as the final optional argument. Rewrite the system prompt to have the model identify domain milestones and emit only specific atomic tasks, each with `title`, `description`, `type`, and `effort_hours`; prohibit dates and offsets. Include the user's target date only as context for scope, not as a field the model may return. When `feedback` is present, append `上次计划校验失败：{feedback}\n请修正后重新生成完整计划。` to the user prompt.

Do not add an orchestration dependency. Retry feedback is supplied by the service in Task 4.

- [ ] **Step 5: Add failing grouping and uniform-capacity scheduling tests**

Add to `backend/tests/test_scheduler.py`:

```python
def test_capacity_groups_multiple_atomic_tasks_on_one_day_and_spans_deadline():
    plan = _plan(
        TaskSpec(title="a", description="x", effort_hours=0.5),
        TaskSpec(title="b", description="x", effort_hours=1.5),
        TaskSpec(title="c", description="x", effort_hours=1.0),
        TaskSpec(title="d", description="x", effort_hours=1.0),
    )
    result = schedule(
        plan,
        date(2026, 8, 14),
        end_date=date(2026, 8, 16),
        daily_hours=2.0,
    )
    assert [item.date for item in result] == [
        date(2026, 8, 14), date(2026, 8, 14),
        date(2026, 8, 16), date(2026, 8, 16),
    ]


def test_capacity_grouping_rejects_fragmentation_that_needs_more_days():
    plan = _plan(*[
        TaskSpec(title=str(i), description="x", effort_hours=effort)
        for i, effort in enumerate([1.5, 1.5, 1.0])
    ])
    with pytest.raises(ValueError, match="3 个自然日"):
        schedule(
            plan,
            date(2026, 8, 13),
            end_date=date(2026, 8, 14),
            daily_hours=2.0,
        )
```

Also assert each resulting date's summed effort is at most 2.0 and cross-milestone flattened order is unchanged.

- [ ] **Step 6: Run scheduler tests and verify RED**

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_scheduler.py -v
```

Expected: current uniform scheduler ignores effort and does not accept `daily_hours`.

- [ ] **Step 7: Implement ordered grouping and group-to-date mapping**

Add:

```python
def group_tasks(plan: PlanSpec, daily_hours: float) -> list[list[tuple[int, int]]]:
    groups = []
    current = []
    used = 0.0
    for mi, milestone in enumerate(plan.milestones):
        for ti, task in enumerate(milestone.tasks):
            if task.effort_hours > daily_hours:
                raise ValueError("单个任务耗时超过每日投入时间")
            if current and used + task.effort_hours > daily_hours + 1e-9:
                groups.append(current)
                current, used = [], 0.0
            current.append((mi, ti))
            used += task.effort_hours
    if current:
        groups.append(current)
    return groups
```

When both `end_date` and `daily_hours` are present, calculate inclusive `day_count`, reject `len(groups) > day_count`, map group index with `round(index * (day_count - 1) / (group_count - 1))`, and assign all group members to that date. Keep the old no-deadline capacity path for legacy requests.

- [ ] **Step 8: Run focused and full backend tests**

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_planner.py tests/test_plan_validation.py tests/test_scheduler.py -v
D:\conda\envs\dl2025\python.exe -m pytest
```

Expected: all pass after updating fixtures that previously included `target_date_offset_days`.

- [ ] **Step 9: Commit Task 3**

```powershell
git add backend/app/llm/schema.py backend/app/llm/planner.py backend/app/services/plan_validation.py backend/app/scheduler/scheduler.py backend/tests/test_planner.py backend/tests/test_plan_validation.py backend/tests/test_scheduler.py backend/tests/test_planner_service.py
git commit -m "feat: plan atomic tasks by daily capacity"
```

---

### Task 4: Daily-Hours API, Regeneration, Capacity Errors, and Rollback

**Files:**
- Modify: `backend/app/api/goals.py`
- Modify: `backend/app/services/planner_service.py`
- Create: `backend/app/services/capacity.py`
- Modify: `backend/tests/test_goals_api.py`
- Modify: `backend/tests/test_planner_service.py`

**Interfaces:**
- API accepts `daily_hours: float = 2.0`.
- Produces: `InsufficientCapacityError` with `required_hours`, `available_hours`, `minimum_days`, and `suggested_duration`.
- `create_goal_with_plan(..., daily_hours: float = 2.0) -> Goal`.
- `generate_plan(..., daily_hours=..., feedback=...)` may be called at most three times for invalid atomic structure.

- [ ] **Step 1: Add failing strict API validation and forwarding tests**

In `backend/tests/test_goals_api.py`, update the fake signature to accept `daily_hours=2.0` and assert omission forwards 2.0. Add:

```python
@pytest.mark.parametrize("daily_hours", [True, "2", 0, -0.5, 0.75, float("inf")])
def test_create_goal_rejects_invalid_daily_hours_without_calling_service(
    client, monkeypatch, daily_hours
):
    called = False
    def fake(*args, **kwargs):
        nonlocal called
        called = True
    monkeypatch.setattr("app.api.goals.create_goal_with_plan", fake)
    response = client.post("/api/goals", json={
        "title": "目标", "duration_value": 7, "duration_unit": "day", "daily_hours": daily_hours,
    })
    assert response.status_code == 422
    assert called is False
```

Add a valid `2.5` forwarding assertion.

- [ ] **Step 2: Run API tests and verify RED**

```powershell
Set-Location backend
D:\conda\envs\dl2025\python.exe -m pytest tests/test_goals_api.py -v
```

Expected: invalid values are ignored as extra fields or the service does not receive `daily_hours`.

- [ ] **Step 3: Add strict daily-hours request validation**

Add `daily_hours: float = 2.0` and a `field_validator("daily_hours", mode="before")`. Reject booleans and non-`int|float`, non-finite values, values `<= 0`, and values not close to a half-hour multiple; return `float(value)`.

Pass the validated value to `create_goal_with_plan()`.

- [ ] **Step 4: Add failing service retry, capacity, and rollback tests**

In `backend/tests/test_planner_service.py`, add:

```python
def test_invalid_atomic_plan_is_regenerated_with_feedback(db_session, monkeypatch):
    invalid = plan_with_efforts(3.0)
    valid = plan_with_efforts(1.0, 1.0)
    calls = []
    def fake(*args, **kwargs):
        calls.append(kwargs)
        return invalid if len(calls) == 1 else valid
    monkeypatch.setattr("app.services.planner_service.generate_plan", fake)
    goal = create_goal_with_plan(
        db_session, "学习交易", duration_value=2, duration_unit="day", daily_hours=2.0
    )
    assert goal.id is not None
    assert len(calls) == 2
    assert "超过每日投入时间" in calls[1]["feedback"]


def test_capacity_shortage_rolls_back_and_reports_suggestion(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.planner_service.generate_plan",
        lambda *a, **k: plan_with_efforts(1.5, 1.5, 1.0),
    )
    with pytest.raises(InsufficientCapacityError) as caught:
        create_goal_with_plan(
            db_session, "目标", duration_value=2, duration_unit="day", daily_hours=2.0
        )
    assert caught.value.required_hours == 4.0
    assert caught.value.available_hours == 4.0
    assert caught.value.minimum_days == 3
    assert db_session.query(Goal).count() == 0
```

Add a successful same-day multi-task case and assert milestone due dates equal their final task dates.

- [ ] **Step 5: Run service tests and verify RED**

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_planner_service.py -v
```

Expected: missing exception/signature failures and no regeneration feedback.

- [ ] **Step 6: Implement capacity details and bounded atomic-plan regeneration**

Create `backend/app/services/capacity.py`:

```python
class InsufficientCapacityError(ValueError):
    def __init__(self, required_hours, available_hours, minimum_days):
        self.required_hours = round(required_hours, 1)
        self.available_hours = round(available_hours, 1)
        self.minimum_days = minimum_days
        self.suggested_duration = {"value": minimum_days, "unit": "day"}
        super().__init__("当前时间不足")

    def as_detail(self):
        return {
            "code": "insufficient_capacity",
            "message": "当前时间不足",
            "required_hours": self.required_hours,
            "available_hours": self.available_hours,
            "minimum_days": self.minimum_days,
            "suggested_duration": self.suggested_duration,
        }
```

In the service, call `generate_plan(..., daily_hours=daily_hours, feedback=feedback)` up to three times until `validate_atomic_plan()` passes. If all fail, raise a clear generation error. For a valid plan, compute total hours, ordered groups, inclusive day count, and `minimum_days = max(math.ceil(total / daily_hours), len(groups))`. Raise `InsufficientCapacityError` before scheduling if `minimum_days > day_count`.

Do all generation, validation, Goal creation, scheduling, and persistence inside the existing rollback-protected `try` block. Move `db.add(goal)` until after valid structure and capacity are known so no transient Goal is needed.

For every milestone, with or without a deadline, set `due_date` to its final scheduled task date; empty milestones use the prior non-empty milestone due date or the plan start date.

- [ ] **Step 7: Return structured 422 capacity details**

In `backend/app/api/goals.py`, catch `InsufficientCapacityError` before the general exception:

```python
except InsufficientCapacityError as exc:
    raise HTTPException(status_code=422, detail=exc.as_detail())
except Exception as exc:
    raise HTTPException(status_code=502, detail=f"计划生成失败：{exc}")
```

Add an API assertion for the exact detail keys and that other generation failures remain 502.

- [ ] **Step 8: Run focused and full backend verification**

```powershell
D:\conda\envs\dl2025\python.exe -m pytest tests/test_goals_api.py tests/test_planner_service.py tests/test_scheduler.py tests/test_planner.py -v
D:\conda\envs\dl2025\python.exe -m pytest
```

Expected: all backend tests pass.

- [ ] **Step 9: Commit Task 4**

```powershell
git add backend/app/api/goals.py backend/app/services/planner_service.py backend/app/services/capacity.py backend/tests/test_goals_api.py backend/tests/test_planner_service.py
git commit -m "feat: enforce daily planning capacity"
```

---

### Task 5: Daily-Hours Form and Structured Capacity Guidance

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/GoalInput.tsx`
- Modify: `frontend/src/pages/GoalInput.test.tsx`

**Interfaces:**
- Extends `CreateGoalInput` with `daily_hours: number`.
- Produces: `ApiError` carrying `status` and parsed `detail`.
- Goal form defaults daily hours to `2`, validates positive half-hour increments, and renders structured shortage guidance.

- [ ] **Step 1: Add failing form and error-display tests**

Extend the successful submission test to assert:

```typescript
const dailyHours = screen.getByLabelText('每日可投入时间') as HTMLInputElement
expect(dailyHours.value).toBe('2')
expect(dailyHours.step).toBe('0.5')
fireEvent.change(dailyHours, { target: { value: '2.5' } })
// Expected createGoal body also contains daily_hours: 2.5
```

Add an `it.each` for `''`, `0`, `-0.5`, and `0.75`, asserting the accessible error text `每日可投入时间必须是 0.5 小时的正数倍` and no API call.

Add:

```typescript
it('shows required capacity and suggested days from a structured API error', async () => {
  mockedApi.createGoal.mockRejectedValue(new ApiError(422, {
    code: 'insufficient_capacity', message: '当前时间不足',
    required_hours: 12, available_hours: 8, minimum_days: 6,
    suggested_duration: { value: 6, unit: 'day' },
  }))
  // submit valid form
  expect(await screen.findByRole('alert')).toHaveTextContent(
    '当前时间不足：计划约需 12 小时，现有周期可用 8 小时。建议至少设置 6 天，或提高每日投入时间。'
  )
})
```

- [ ] **Step 2: Run GoalInput tests and verify RED**

```powershell
Set-Location frontend
npm.cmd test -- src/pages/GoalInput.test.tsx
```

Expected: missing input/type/error failures.

- [ ] **Step 3: Preserve structured API errors**

In `frontend/src/api/client.ts`, add:

```typescript
export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : '请求失败')
  }
}
```

Parse the response once. Throw `new ApiError(res.status, payload.detail ?? res.statusText)`. Extend `CreateGoalInput` with `daily_hours`.

- [ ] **Step 4: Add the daily-hours control and validation**

In `GoalInput`, add state defaulting to `'2'`, a label/input with `type="number"`, `min={0.5}`, `step={0.5}`, and accessible error linkage. Accept a number only when finite, positive, and `Number.isInteger(value * 2)`. Submit `daily_hours`.

When catching `ApiError`, detect a detail object whose `code === 'insufficient_capacity'` and render the exact Chinese guidance from the test; otherwise retain the existing message behavior.

- [ ] **Step 5: Run focused tests, all frontend tests, and build**

```powershell
npm.cmd test -- src/pages/GoalInput.test.tsx
npm.cmd test
npm.cmd run build
```

Expected: all pass and build exits 0.

- [ ] **Step 6: Commit Task 5**

```powershell
git add frontend/src/api/client.ts frontend/src/pages/GoalInput.tsx frontend/src/pages/GoalInput.test.tsx
git commit -m "feat: configure daily planning hours"
```

---

### Task 6: Verification Loading Progress, Retry, and Detailed Results

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/VerificationModal.tsx`
- Create: `frontend/src/components/VerificationModal.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Extends `VerificationResult` with optional `points` and `details` for test mode.
- The modal has distinct `generating` and `submitting` states.
- A retry button restarts only verification generation for the current task.

- [ ] **Step 1: Add failing loading, success, failure, and result tests**

Create a deferred-promise helper and mock `api.getVerification`/`submitVerification`. Add tests that:

```typescript
it('shows an indeterminate progress bar and no submit button while generating', () => {
  mockedApi.getVerification.mockReturnValue(deferred.promise)
  render(<VerificationModal task={task} onClose={vi.fn()} />)
  expect(screen.getByRole('progressbar', { name: '正在生成 10 道题' })).toBeTruthy()
  expect(screen.getByText('正在生成 10 道题…')).toBeTruthy()
  expect(screen.queryByRole('button', { name: '提交检验' })).toBeNull()
})
```

Resolve with seven public choice questions and three public short questions; assert all ten texts and the submit button appear. Reject once; assert an error and `重新生成` button, click it, and assert `getVerification` is called twice. Submit a result containing `points: 70` and ten details; assert `总分：70 / 100`, choice correctness, and short feedback render.

- [ ] **Step 2: Run modal tests and verify RED**

```powershell
Set-Location frontend
npm.cmd test -- src/components/VerificationModal.test.tsx
```

Expected: no progress bar/retry/detailed result behavior exists.

- [ ] **Step 3: Implement explicit generation state and retry**

Use:

```typescript
const [generating, setGenerating] = useState(true)
const [generationAttempt, setGenerationAttempt] = useState(0)
```

The effect clears content/error, sets generating true, calls the API, ignores updates after unmount, and sets generating false in `finally`. While generating, render:

```tsx
<div className="verification-loading">
  <p>正在生成 10 道题…</p>
  <div
    className="verification-progress"
    role="progressbar"
    aria-label="正在生成 10 道题"
    aria-valuetext="生成中"
  ><span /></div>
</div>
```

On load error, render `重新生成`; clicking increments `generationAttempt`. Do not render the answer form or submit button unless content is non-null and generation succeeded.

- [ ] **Step 4: Add the indeterminate progress animation and reduced-motion behavior**

Add CSS with a stationary track and a translating 35%-width bar. Use `@media (prefers-reduced-motion: reduce)` to disable translation and use a subtle opacity pulse instead. Keep colors aligned with existing `--border` and `--accent` variables.

- [ ] **Step 5: Render transparent result details**

Extend frontend types:

```typescript
export interface QuizQuestionResultDTO {
  id: number
  type: 'choice' | 'short'
  points: number
  correct?: boolean | null
  correct_answer?: string | null
  feedback: string
}

export interface VerificationResult {
  passed: boolean
  score: number
  feedback: string
  verified: boolean
  points?: number
  details?: QuizQuestionResultDTO[]
}
```

In test-mode results, show total points and one row per detail. Show choice `正确/错误` and the correct answer after submission; show short-answer points and feedback. Delivery-mode results retain the current summary.

- [ ] **Step 6: Run focused tests, full frontend tests, and build**

```powershell
npm.cmd test -- src/components/VerificationModal.test.tsx
npm.cmd test
npm.cmd run build
```

Expected: all pass and production build exits 0.

- [ ] **Step 7: Commit Task 6**

```powershell
git add frontend/src/types.ts frontend/src/components/VerificationModal.tsx frontend/src/components/VerificationModal.test.tsx frontend/src/index.css
git commit -m "feat: show verification generation progress"
```

---

### Task 7: Documentation and End-to-End Verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents daily-hours input, autonomous atomic decomposition, capacity shortage behavior, ten-question verification, and 70-point scoring.

- [ ] **Step 1: Add concise behavior documentation**

Append under `## 排程规则`:

```markdown
创建目标时还可填写每日可投入时间，默认 2 小时。AI 会自行识别目标涉及的领域，把宽泛内容拆成以 0.5 小时为粒度的具体子任务；每天的任务数量可以不同，但累计预计耗时不会超过每日预算。任务组仍会包含周末地均匀铺满整个预期周期。若周期容量不足，系统不会创建计划，而会显示所需小时数和建议的最短天数。

学习任务的每次检验会重新生成 10 道题（7 道选择题、3 道简答题）。每题 10 分：选择题由服务端按正确答案计分，简答题由 AI 按评分点逐题计分；总分达到 70 分即通过。
```

Keep the DeepSeek key example as `DEEPSEEK_API_KEY`; do not reintroduce another provider name.

- [ ] **Step 2: Run fresh full verification**

From the feature worktree root:

```powershell
Push-Location backend
D:\conda\envs\dl2025\python.exe -m pytest
Pop-Location
Push-Location frontend
npm.cmd test
npm.cmd run build
Pop-Location
git diff --check
```

Expected: all backend tests pass, all frontend tests pass, the build exits 0, and `git diff --check` prints no errors.

- [ ] **Step 3: Perform a manual non-secret smoke check**

Start the backend with the user-level `DEEPSEEK_API_KEY` injected and start Vite on 5173. Confirm without printing the key:

1. Goal form shows daily hours default 2.
2. A small generated plan contains concrete subknowledge tasks and no day exceeds the selected hours.
3. Opening learning verification shows the progress bar, then exactly 10 questions.
4. Reopening verification produces no exact duplicate question text for the same task.
5. A submitted result shows points and per-question details.

Do not include quiz answers, the API key, or raw model payloads in logs or reports.

- [ ] **Step 4: Commit documentation**

```powershell
git add README.md
git commit -m "docs: explain adaptive plans and quiz scoring"
```

- [ ] **Step 5: Request final code review**

Review the full range from `e1338b6` through the Task 7 commit against both approved specs. Treat leaked private answers, incorrect 70-point boundaries, unbounded model retry, daily capacity overflow, missing rollback, or model-owned dates as blocking findings. Re-run full verification after any review fix.
