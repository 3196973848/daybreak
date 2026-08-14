# Task-Scoped AI Tutor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, task-scoped DeepSeek tutor for `learn` tasks, with adaptive teaching, resumable history, idempotent turns, and direct access to the existing verification flow.

**Architecture:** Store one `LearningSession` per learning task plus immutable `LearningTurn` rows. A strict tutor adapter owns DeepSeek prompting, validation, and bounded retries; a service layer owns task eligibility, rolling context, idempotency, and transactions; a focused FastAPI router exposes session/start/turn endpoints. The React learning page consumes those endpoints, renders safe Markdown without raw HTML, and reuses `VerificationModal`; no LangGraph is introduced.

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic 2, OpenAI-compatible DeepSeek client, pytest, React 18, TypeScript, React Router 6, `react-markdown`, Vitest, Testing Library, Vite.

## Global Constraints

- Work only in `D:\planagent\.worktrees\duration-uniform-scheduling` on the existing feature branch.
- Follow `docs/superpowers/specs/2026-08-14-task-tutor-learning-design.md`; do not add web search, uploads, voice, global tutoring, reset, multi-user support, or new task-completion rules.
- Use strict TDD for every task: add the stated test, run it and capture the expected failure, implement the smallest production change, then rerun focused and relevant full suites.
- Preserve the current DeepSeek/OpenAI-compatible settings. Never print or commit API keys, model raw failures, prompts containing private data, or database parameter values.
- All model and persistence failures exposed by the new API use stable Chinese messages and HTTP 502. Roll back before responding.
- Only the existing verification result may mark a task done. `ready_for_verification` is advisory and sticky.
- Persist full history, but send only the rolling summary plus the most recent 12 turns to DeepSeek.
- Do not add LangGraph. Add only `react-markdown`; never enable `rehypeRaw` or otherwise execute model-produced HTML.
- After each task run `git diff --check`, inspect `git status --short`, and commit only that task's files with the specified message.

---

## Task 1: Persist Learning Sessions and Turns

**Files:**

- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_models.py`

### Data contract

Add these ORM models and relationships:

```python
class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), unique=True)
    stage: Mapped[str] = mapped_column(String(20), default="diagnose")
    session_summary: Mapped[str] = mapped_column(Text, default="")
    covered_points: Mapped[str] = mapped_column(Text, default="[]")
    weak_points: Mapped[str] = mapped_column(Text, default="[]")
    ready_for_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_hours_snapshot: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    task: Mapped["Task"] = relationship(back_populates="learning_session")
    turns: Mapped[list["LearningTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LearningTurn.id",
    )


class LearningTurn(Base):
    __tablename__ = "learning_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "client_turn_id", name="uq_learning_turn_client"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("learning_sessions.id"))
    client_turn_id: Mapped[str] = mapped_column(String(64))
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_message: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    session: Mapped[LearningSession] = relationship(back_populates="turns")
```

Also add `Task.learning_session` as a one-to-one, delete-orphan relationship.

### Steps

- [ ] Extend `backend/tests/test_models.py` with an exact round-trip and uniqueness test:

```python
import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import LearningSession, LearningTurn


def test_learning_session_roundtrip_and_turn_order(db_session):
    task = _learning_task(db_session)
    task.learning_session = LearningSession(
        stage="explain",
        session_summary="已诊断基础",
        covered_points=json.dumps(["规则定义"], ensure_ascii=False),
        weak_points=json.dumps(["边界条件"], ensure_ascii=False),
        ready_for_verification=False,
        estimated_hours_snapshot=2.0,
        turns=[
            LearningTurn(
                client_turn_id="initial",
                user_message=None,
                assistant_message="你目前如何理解这条规则？",
                stage="diagnose",
            ),
            LearningTurn(
                client_turn_id="turn-1",
                user_message="我理解为……",
                assistant_message="先澄清定义。",
                stage="explain",
            ),
        ],
    )
    db_session.commit()
    db_session.expire_all()

    got = db_session.get(Task, task.id).learning_session
    assert got.estimated_hours_snapshot == 2.0
    assert [turn.client_turn_id for turn in got.turns] == ["initial", "turn-1"]
    assert json.loads(got.covered_points) == ["规则定义"]


def test_learning_session_and_client_turn_ids_are_unique(db_session):
    first_task = _learning_task(db_session)
    first_task.learning_session = LearningSession(
        estimated_hours_snapshot=1.0,
        turns=[LearningTurn(
            client_turn_id="same-id", user_message=None,
            assistant_message="诊断", stage="diagnose",
        )],
    )
    db_session.commit()

    db_session.add(LearningTurn(
        session_id=first_task.learning_session.id,
        client_turn_id="same-id", user_message="重复",
        assistant_message="不应保存", stage="explain",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] Add a local `_learning_task` fixture helper using the existing Goal → Plan → Milestone → Task construction. Do not alter global fixtures.
- [ ] Run RED:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_models.py -v
```

Expected: import/model/relationship failures because `LearningSession` and `LearningTurn` do not exist.

- [ ] Add `UniqueConstraint` to the SQLAlchemy imports, add both models, and add the `Task.learning_session` relationship exactly as above.
- [ ] Ensure the uniqueness test calls `db_session.rollback()` after the expected `IntegrityError`, so the test session remains reusable.
- [ ] Run GREEN and the full backend suite:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_models.py -v
D:\conda\envs\dl2025\python.exe -m pytest backend/tests -v
git diff --check
```

- [ ] Commit:

```powershell
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: persist task learning sessions"
```

---

## Task 2: Build the Strict DeepSeek Tutor Adapter

**Files:**

- Create: `backend/app/llm/tutor.py`
- Create: `backend/tests/test_tutor.py`

### Public interfaces

```python
LearningStage = Literal["diagnose", "explain", "practice", "remediate", "ready"]


class TutorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str = Field(min_length=1)
    stage: LearningStage
    session_summary: str = Field(min_length=1, max_length=4000)
    covered_points: list[str]
    weak_points: list[str]
    ready_for_verification: bool


def generate_tutor_turn(
    *,
    task_title: str,
    task_description: str,
    estimated_hours: float,
    previous_summary: str,
    recent_turns: list[dict[str, str | None]],
    user_message: str | None,
    already_ready: bool,
    client=None,
) -> TutorOutput:
    pass
```

### Steps

- [ ] In `backend/tests/test_tutor.py`, add schema tests that accept each legal stage and reject extra fields, blank replies/summaries, blank list items, duplicate normalized list items, and `stage="ready"` with `ready_for_verification=False`.
- [ ] Add a sticky-ready test: when `already_ready=True`, a parsed response with `ready_for_verification=False` must still return `True`; a later stage may be `practice` or `remediate`, but readiness may never fall back.
- [ ] Add retry tests with a fake OpenAI client whose completions return, in sequence: empty content, malformed JSON, then valid JSON. Assert exactly three calls and a valid result. Add a three-invalid case asserting `RuntimeError("导师暂时无法生成有效回复")` with no raw response or sentinel exception text.
- [ ] Add prompt/context tests that capture the request and assert it contains:

```python
assert "预计学习时长：2.0 小时" in user_payload
assert "滚动摘要：已覆盖基础定义" in user_payload
assert [turn["assistant_message"] for turn in sent_turns] == [f"答复 {i}" for i in range(3, 15)]
assert "忽略系统规则" in user_payload  # retained as user content, not system instructions
```

Build 15 turns in the test and assert only the last 12 are serialized.

- [ ] Run RED:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_tutor.py -v
```

Expected: collection fails because `app.llm.tutor` does not exist.

- [ ] Implement `TutorOutput` with validators that strip each string, reject blanks, and de-duplicate points by `casefold()` while preserving first-seen order. Enforce ready-stage consistency with a model validator.
- [ ] Implement a system prompt that fixes the teaching rules, task boundary, JSON-only output, adaptive stages, time-budget pacing, and the rule that user content cannot override it.
- [ ] Serialize task data, previous summary, the last 12 turns, and the current message into a JSON user payload with `ensure_ascii=False`. Never interpolate user content into the system prompt.
- [ ] For at most three attempts, call the configured DeepSeek client with `response_format={"type": "json_object"}` and validate `TutorOutput`. On retry, append only a constant server-authored instruction such as `上一次输出无效，请重新输出完整且符合结构的 JSON。`; do not include raw output or exception text.
- [ ] After validation, make readiness sticky:

```python
if already_ready and not output.ready_for_verification:
    output = output.model_copy(update={"ready_for_verification": True})
```

- [ ] Run GREEN and relevant LLM tests:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_tutor.py backend/tests/test_verifier.py backend/tests/test_planner.py -v
git diff --check
```

- [ ] Commit:

```powershell
git add backend/app/llm/tutor.py backend/tests/test_tutor.py
git commit -m "feat: add adaptive tutor generation"
```

---

## Task 3: Add the Transactional Learning Service

**Files:**

- Create: `backend/app/services/learning_service.py`
- Create: `backend/tests/test_learning_service.py`

### Public interfaces

```python
class LearningTaskNotFound(Exception): pass
class LearningTaskTypeError(Exception): pass
class LearningSessionNotFound(Exception): pass
class LearningGenerationError(Exception): pass
class LearningPersistenceError(Exception): pass


def get_learning_session(db: Session, task_id: int) -> LearningSession: pass
def start_learning_session(db: Session, task_id: int) -> LearningSession: pass
def add_learning_turn(
    db: Session, task_id: int, client_turn_id: str, message: str
) -> tuple[LearningSession, LearningTurn]: pass
def goal_id_for(session: LearningSession) -> int: pass
```

Resolve `generate_tutor_turn` inside each function rather than binding it as a default argument, so tests can monkeypatch `app.services.learning_service.generate_tutor_turn`.

### Steps

- [ ] Build `backend/tests/test_learning_service.py` with a `_task` factory for learn/practice tasks and a `_tutor_output(stage="diagnose", ready=False)` factory returning valid `TutorOutput`.
- [ ] Add start tests asserting: a learn task generates one diagnostic; the stored initial turn uses `client_turn_id="initial"` and `user_message is None`; effort is snapshotted; starting twice returns the same session and calls the tutor once; missing task and non-learn task fail before model invocation.
- [ ] Add turn tests asserting: the service sends the summary and only the latest 12 persisted turns; a `practice → remediate` transition is stored; covered/weak points replace the stored JSON arrays; `ready_for_verification` remains true after later remediation.
- [ ] Add idempotency tests using the same `client_turn_id` twice. Assert the second call returns the saved turn, the tutor call count stays one, and only one database row exists.
- [ ] Add failure tests for both start and turn:

```python
@pytest.mark.parametrize("method_name", ["flush", "refresh", "commit"])
def test_turn_persistence_failure_rolls_back_and_session_remains_reusable(
    db_session, monkeypatch, method_name
):
    # force the selected method to raise after generation
    # assert no turn/state update survived
    # restore the method and retry with the same client_turn_id
    # assert retry succeeds exactly once
```

Also assert model failure creates no session/turn and does not mutate an existing session.

- [ ] Run RED:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_learning_service.py -v
```

Expected: import failure because the service module does not exist.

- [ ] Implement task lookup and eligibility in one helper. `get_learning_session` must return not-found only after confirming the task exists and is type `learn`.
- [ ] Implement start in this order: validate task → return existing session → call tutor → construct session and initial turn → `add`/`flush`/`refresh`/`commit` inside one `try` → rollback and raise `LearningPersistenceError` on any database exception. Do not insert an empty session before model success.
- [ ] Implement turn creation in this order: validate task/session → return matching saved idempotency key → trim/validate message → build context from `session.turns[-12:]` → call tutor → update session plus add one turn → `flush`/`refresh`/`commit` in one rollback-protected block.
- [ ] Store point arrays with `json.dumps(points, ensure_ascii=False)` and decode with a small private helper that safely returns `[]` for impossible legacy corruption without changing the stored history.
- [ ] Map all adapter `RuntimeError` failures to `LearningGenerationError` without copying exception text. Map SQLAlchemy/persistence failures to `LearningPersistenceError` without copying exception text.
- [ ] Run GREEN and full backend suite:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_learning_service.py -v
D:\conda\envs\dl2025\python.exe -m pytest backend/tests -v
git diff --check
```

- [ ] Commit:

```powershell
git add backend/app/services/learning_service.py backend/tests/test_learning_service.py
git commit -m "feat: manage persistent tutor sessions"
```

---

## Task 4: Expose Learning Session APIs

**Files:**

- Create: `backend/app/api/learning.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_learning_api.py`

### HTTP schemas

```python
class LearningTurnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_turn_id: UUID
    message: str = Field(min_length=1, max_length=10000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value


class LearningTurnResponse(BaseModel):
    id: int
    client_turn_id: str
    user_message: str | None
    assistant_message: str
    stage: LearningStage
    created_at: datetime


class LearningSessionResponse(BaseModel):
    id: int
    task_id: int
    goal_id: int
    task_title: str
    task_description: str
    stage: LearningStage
    covered_points: list[str]
    weak_points: list[str]
    ready_for_verification: bool
    estimated_hours_snapshot: float
    turns: list[LearningTurnResponse]
```

### Steps

- [ ] In `backend/tests/test_learning_api.py`, add GET tests for full ordered history and `goal_id`, 404 before start/missing task, and 422 for a practice/project task.
- [ ] Add POST-start tests for initial creation and idempotent resume. Monkeypatch the tutor adapter and assert the public response never contains `session_summary`, prompts, raw model JSON, or internal exception text.
- [ ] Add POST-turn tests for a successful response, trimmed input, UUID idempotent retry, missing session 404, blank/extra/invalid UUID payload 422, and non-learn 422.
- [ ] Add model and persistence failure API tests with sentinel strings. Assert exact stable bodies:

```python
assert response.status_code == 502
assert response.json() == {"detail": "导师回复生成失败，请稍后重试"}
assert sentinel not in response.text
```

For start persistence failure use `导师会话保存失败，请稍后重试`; for turn persistence failure use `导师回复保存失败，请稍后重试`. Verify zero partial rows and successful reuse after restoring the DB method.

- [ ] Run RED:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_learning_api.py -v
```

Expected: all endpoints return 404 because the router is absent.

- [ ] Create a router with `prefix="/api/tasks"` and implement:

```python
@router.get("/{task_id}/learning-session", response_model=LearningSessionResponse)
def read_learning_session(task_id: int, db: Session = Depends(get_db)): pass

@router.post("/{task_id}/learning-session", response_model=LearningSessionResponse)
def begin_learning_session(task_id: int, db: Session = Depends(get_db)): pass

@router.post("/{task_id}/learning-session/turns", response_model=LearningSessionResponse)
def create_learning_turn(task_id: int, body: LearningTurnCreate, db: Session = Depends(get_db)): pass
```

- [ ] Use one private serializer that JSON-decodes point arrays, emits full ordered turns, and derives `goal_id` through `task.milestone.plan.goal_id`. Do not expose `session_summary`.
- [ ] Catch only the service's public exception classes and map them to 404/422/502. Never use `str(exc)` in HTTP details or logs.
- [ ] Include the router in `backend/app/main.py`.
- [ ] Run GREEN and full backend suite:

```powershell
D:\conda\envs\dl2025\python.exe -m pytest backend/tests/test_learning_api.py -v
D:\conda\envs\dl2025\python.exe -m pytest backend/tests -v
git diff --check
```

- [ ] Commit:

```powershell
git add backend/app/api/learning.py backend/app/main.py backend/tests/test_learning_api.py
git commit -m "feat: expose task tutor APIs"
```

---

## Task 5: Add Frontend Contracts and the Learning Page

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/router.tsx`
- Create: `frontend/src/pages/LearningPage.tsx`
- Create: `frontend/src/pages/LearningPage.test.tsx`
- Modify: `frontend/src/index.css`

### Frontend contracts

```typescript
export type LearningStage = 'diagnose' | 'explain' | 'practice' | 'remediate' | 'ready'

export interface LearningTurnDTO {
  id: number
  client_turn_id: string
  user_message: string | null
  assistant_message: string
  stage: LearningStage
  created_at: string
}

export interface LearningSessionDTO {
  id: number
  task_id: number
  goal_id: number
  task_title: string
  task_description: string
  stage: LearningStage
  covered_points: string[]
  weak_points: string[]
  ready_for_verification: boolean
  estimated_hours_snapshot: number
  turns: LearningTurnDTO[]
}
```

API methods:

```typescript
getLearningSession: (taskId: number) =>
  req<LearningSessionDTO>(`/tasks/${taskId}/learning-session`),
startLearningSession: (taskId: number) =>
  req<LearningSessionDTO>(`/tasks/${taskId}/learning-session`, { method: 'POST' }),
sendLearningTurn: (taskId: number, body: { client_turn_id: string; message: string }) =>
  req<LearningSessionDTO>(`/tasks/${taskId}/learning-session/turns`, {
    method: 'POST', body: JSON.stringify(body),
  }),
```

### Steps

- [ ] Install the one approved dependency from `frontend`:

```powershell
npm.cmd install react-markdown
```

Confirm `package.json` and the lockfile change only add `react-markdown` and its transitive packages; do not add `rehypeRaw`.

- [ ] Write `LearningPage.test.tsx` with mocked API and MemoryRouter coverage for:

  - GET restores a full existing conversation and shows stage, hours, covered and weak points.
  - GET 404 triggers POST start, shows `导师正在准备诊断问题`, then renders the first diagnostic.
  - user submission sends one UUID and disables duplicate submission while showing `导师正在思考`.
  - failed send preserves the textarea and UUID; clicking `重试` sends the identical body; success clears it.
  - ready state shows `建议开始检验`; non-ready state does not.
  - Markdown paragraphs, lists, and fenced code render; `<script>alert(1)</script>` appears only as text and no `script` node exists.
  - desktop contains `.learning-layout` with status and chat regions; `.learning-status-card` precedes chat in DOM for accessible mobile ordering.

Use a deterministic test stub for `crypto.randomUUID`:

```typescript
vi.stubGlobal('crypto', { randomUUID: vi.fn(() => '11111111-1111-4111-8111-111111111111') })
```

- [ ] Run RED before adding the page/contracts:

```powershell
Set-Location frontend
npm.cmd test -- --run src/pages/LearningPage.test.tsx
```

Expected: module/import failures for `LearningPage` and learning DTO/API methods.

- [ ] Add the DTOs and three API methods exactly above. Keep `ApiError.status` available so the page can distinguish 404 from real load failures.
- [ ] Implement `LearningPage` route `/tasks/:taskId/learn`. On mount: GET; only on `ApiError` 404 call POST start. Protect both effects with an `active` flag so stale responses cannot update a changed task route.
- [ ] Store pending submission as `{ client_turn_id, message }`. Create it once on initial send, reuse it on retry, and clear it only after success. Disable the textarea/send button while loading or sending.
- [ ] Render each assistant message with:

```tsx
<ReactMarkdown skipHtml>{turn.assistant_message}</ReactMarkdown>
```

Do not supply `rehypeRaw`, `dangerouslySetInnerHTML`, or custom components that execute links/scripts.
- [ ] Add the approved two-column CSS under dedicated `learning-*` classes. Use a status card column and a conversation column; at `max-width: 720px`, switch to one column with the status card first. Add visible focus states and `aria-live="polite"` for loading/thinking status.
- [ ] Add the router entry, then run GREEN, full frontend, and build:

```powershell
npm.cmd test -- --run src/pages/LearningPage.test.tsx
npm.cmd test
npm.cmd run build
Set-Location ..
git diff --check
```

- [ ] Commit:

```powershell
git add frontend/package.json frontend/package-lock.json frontend/src/types.ts frontend/src/api/client.ts frontend/src/router.tsx frontend/src/pages/LearningPage.tsx frontend/src/pages/LearningPage.test.tsx frontend/src/index.css
git commit -m "feat: add persistent tutor learning page"
```

---

## Task 6: Connect Daily Tasks and Existing Verification

**Files:**

- Modify: `frontend/src/pages/DailyTasks.tsx`
- Modify: `frontend/src/pages/DailyTasks.test.tsx`
- Modify: `frontend/src/pages/LearningPage.tsx`
- Modify: `frontend/src/pages/LearningPage.test.tsx`

### Steps

- [ ] Extend `DailyTasks.test.tsx` with one `learn` task and mock `api.getLearningSession`. Assert a 404 session check labels the link `开始学习` and points to `/tasks/7/learn`; an existing session labels it `继续学习`. Assert practice/project tasks have no learning link.
- [ ] Ensure the session-label lookup runs once per visible learn task, tolerates non-404 failures by retaining `开始学习`, and does not block the task list.
- [ ] Extend `LearningPage.test.tsx` to click `开始检验`, assert `VerificationModal` opens for the current learn task, and verify the top return link targets `/goals/{goal_id}/daily`.
- [ ] Add a verification success regression: mock the modal's `onVerified` result with `passed: true`, assert the page shows `检验已通过` and disables or relabels the verification action; a failed result must not claim completion. The modal itself remains the sole caller of the existing verification API.
- [ ] Run RED:

```powershell
Set-Location frontend
npm.cmd test -- --run src/pages/DailyTasks.test.tsx src/pages/LearningPage.test.tsx
```

Expected: no learning entry, no verification action/modal, and no back link yet.

- [ ] In `DailyTasks`, use `Link` from React Router and a `Record<number, boolean>` state for detected existing sessions. For each learn task call `api.getLearningSession`; status 200 means continue, 404 means start. Render no tutor entry for other task types.
- [ ] In `LearningPage`, reconstruct the minimal `TaskDTO` required by `VerificationModal` from the session response (`type: 'learn'`, effort snapshot, existing safe defaults for unused fields). Keep `VerificationModal` unchanged.
- [ ] Always show `开始检验`; additionally show `建议开始检验` when `ready_for_verification` is true. On a passed callback, update only local success UI; rely on the existing verification backend to mark the task complete.
- [ ] Run focused and full frontend verification:

```powershell
npm.cmd test -- --run src/pages/DailyTasks.test.tsx src/pages/LearningPage.test.tsx src/components/VerificationModal.test.tsx
npm.cmd test
npm.cmd run build
Set-Location ..
git diff --check
```

- [ ] Commit:

```powershell
git add frontend/src/pages/DailyTasks.tsx frontend/src/pages/DailyTasks.test.tsx frontend/src/pages/LearningPage.tsx frontend/src/pages/LearningPage.test.tsx
git commit -m "feat: connect tutor to daily learning tasks"
```

---

## Task 7: Document, Verify, and Smoke-Test the Tutor Flow

**Files:**

- Modify: `README.md`
- Create: `docs/superpowers/reports/2026-08-14-task-tutor-learning-report.md`

### Steps

- [ ] Add a concise README section describing: task-scoped tutor entry, persistent adaptive conversation, DeepSeek configuration reuse, advisory readiness, existing 70/100 verification completion, and the explicit first-version exclusions. Do not claim web grounding or file support.
- [ ] Run fresh automated verification from clean processes:

```powershell
Set-Location backend
D:\conda\envs\dl2025\python.exe -m pytest -v
Set-Location ..\frontend
npm.cmd test
npm.cmd run build
Set-Location ..
git diff --check
git status --short
```

Expected: all backend tests pass, all frontend tests pass, production build succeeds, and only README/report changes remain.

- [ ] Start backend and frontend with the configured environment, without printing the key:

```powershell
Set-Location backend
D:\conda\envs\dl2025\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

- [ ] Using a real `learn` task, manually verify:

  1. Daily Tasks shows `开始学习`; entering creates a diagnostic question.
  2. A learner answer changes the next explanation or exercise; status lists update without a fake percentage.
  3. Refresh restores every displayed turn and changes the entry to `继续学习`.
  4. Simulated network retry with the same browser pending action does not create a duplicate turn.
  5. The verification modal can open before readiness; a failed score does not complete the task.
  6. After readiness, the suggestion appears; a passing verification completes the task and the existing circular check remains correct.
  7. Mobile-width layout places the status card above the conversation.

- [ ] Record exact commands, pass counts, build result, smoke observations, commit hashes for Tasks 1–6, and any non-blocking warnings in the report. Do not include API keys, full model prompts, or private quiz answer data.
- [ ] Request a read-only code review covering the complete range from the design commit through the current HEAD. Resolve every Critical/Important finding with a new RED/GREEN commit and update the report before completion.
- [ ] Run the final fresh suite again after any review fixes.
- [ ] Commit documentation and report:

```powershell
git add README.md docs/superpowers/reports/2026-08-14-task-tutor-learning-report.md
git commit -m "docs: document task tutor workflow"
```

- [ ] Confirm final state:

```powershell
git status --short
git log --oneline -8
```

Expected: no tracked changes and a linear series of focused tutor commits.

---

## Final Acceptance Checklist

- [ ] Only `learn` tasks expose task-scoped tutoring.
- [ ] One session persists per task, full history resumes, and duplicate turn IDs do not call DeepSeek twice.
- [ ] DeepSeek receives summary plus at most 12 recent turns and retries invalid structured output no more than three times.
- [ ] Readiness is sticky and advisory; only the existing verification pass completes a task.
- [ ] All start/turn persistence boundaries roll back cleanly and 502 responses reveal no model/database internals.
- [ ] Tutor Markdown cannot execute raw HTML or script.
- [ ] Desktop and mobile learning layouts match the approved dedicated-page design.
- [ ] Backend, frontend, build, diff check, manual smoke, and independent review all pass.
