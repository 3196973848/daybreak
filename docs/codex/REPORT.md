# PlanAgent 后端实现报告

## 任务提交

| 任务 | 提交 | 卡内验收 |
| --- | --- | --- |
| Task 01 后端脚手架与健康检查 | `195187b` | `1 passed, 1 warning in 0.04s` |
| Task 02 SQLAlchemy 数据模型 | `cd5f40e` | `1 passed, 1 warning in 0.05s` |
| Task 03 确定性排程算法 | `b752cc0` | `3 passed, 1 warning in 0.03s` |
| Task 04 LLM 计划生成 | `f002ba1` | `1 passed, 1 warning in 1.76s` |
| Task 05 计划生成服务 | `834156c` | `1 passed, 1 warning in 1.50s` |
| Task 06 Goals REST API | `707cf99` | `4 passed, 1 warning in 0.13s` |
| Task 07 LLM 检验模块 | `6d467c6` | `4 passed, 2 warnings in 0.03s` |
| Task 08 Tasks REST API | `713aad7` | `4 passed, 2 warnings in 0.09s` |

每张任务卡的“报告”区已分别记录提交 hash、pytest 摘要与 concerns。八个后端任务均使用任务卡指定的 commit message 独立提交；共享分支上的前端提交与后端提交在历史中交错。

## 全量测试

在 `backend/` 目录执行：

```text
D:\conda\envs\dl2025\python.exe -m pytest
20 passed, 3 warnings in 0.23s
```

全量测试收集 20 项，覆盖健康检查、ORM 往返、调度、计划生成、计划服务、Goals API、Tasks API 与测试/交付检验流程。

## 实施中修正

- Task 01 的 `init_db()` 在 Task 02 前已引用 `app.models`；为使 Task 01 可独立启动，先提交最小占位模块，Task 02 随后用正式模型替换。
- Task 06 的内存 SQLite 测试需跨 FastAPI 工作线程共享同一连接，因此测试 engine 使用 `StaticPool`。
- Task 06 卡内首个 fake 遗漏权威服务接口的 `db` 参数，已修正测试 fake 签名。
- 删除 Goal 时需删除其唯一 Plan 及后代；已在 Goal→Plan 关系增加 `cascade="all, delete-orphan"`，避免把非空 `plans.goal_id` 更新为 `NULL`。

## 遗留问题与集成提醒

- 当前执行环境不允许在受限沙箱内写 `backend/`，pytest 的 SQLite/缓存写入均经批准在沙箱外执行。
- 全量测试有 3 条 warning：1 条 FastAPI/Starlette `TestClient` 弃用提示；2 条由任务卡规定的 Pydantic 类名 `TestContent` 触发的 pytest 收集提示。
- LLM 单元测试使用 fake client，不调用真实 Anthropic 服务；真实凭据、网络和模型可用性留给集成验证。
- 在八个后端提交完成后，共享工作树出现未提交的并发改动：将 Anthropic `messages.parse`/`claude-opus-4-8` 改为 OpenAI 兼容的 DeepSeek `chat.completions`，涉及 `backend/app/config.py`、`backend/app/llm/planner.py`、`backend/app/llm/verifier.py`、`backend/requirements.txt` 及对应测试。这与总交接文档的 Anthropic 全局约束冲突，且不属于上述八个后端提交；为避免覆盖另一实现者的工作，本次未回滚或纳入报告提交。集成 review 应决定保留任务提交中的 Anthropic 实现，还是正式变更全局设计。
