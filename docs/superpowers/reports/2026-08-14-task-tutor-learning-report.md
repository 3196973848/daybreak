# 2026-08-14 任务级 AI 导师 — 交付报告

## 目标

为 `learn` 类型任务提供持久化、可续聊、幂等的任务级 AI 导师：自适应推进阶段、滚动上下文、仅建议性 readiness，并复用既有检验流程判定任务完成。

## 提交

| 任务 | 提交 | 说明 |
| --- | --- | --- |
| Task 1 持久化学习会话 | `06faf75` | `LearningSession` / `LearningTurn` 模型与唯一约束 |
| Task 2 导师适配器 | `036f1ef` | 严格 `TutorOutput`、滚动 12 轮上下文、≤3 次重试 |
| Task 3 学习服务 | `97e7d9c` | 事务边界、幂等、异常映射 |
| Task 4 学习 API | `bf9d250` | GET/POST session、POST turn，稳定错误体 |
| 修复：会话幂等加固 | `109811c` | 并发 start/turn 幂等 |
| 修复：初始诊断轮必答 | `9713478` | 首次启动必须生成诊断轮 |
| Task 5 学习页（前端） | `d03267b` | LearningPage、DTO、路由（并入 UI 提交） |
| Task 6 每日任务接入与检验打通 | `36abdd2` | 开始/继续学习入口、检验弹窗、通过态 |
| pytest 临时目录修复 | `49f51ac` | 项目内 `.pytest_tmp`，默认命令全绿 |
| 评审修复 | `73ea445` | 见下方「代码评审」 |

## 自动化验证

后端（`backend/`）：

```text
D:\conda\envs\dl2025\python.exe -m pytest -q
179 passed, 3 warnings in 4.22s
```

前端（`frontend/`）：

```text
npm.cmd test
4 test files / 41 tests passed

npm.cmd run build
✓ 208 modules transformed, build succeeded
```

`git diff --check` 无空白错误。

## 代码评审（双轴）

- **Standards**：未发现硬性违规。一处判断型坏味道：`api/learning.py::_points` 与 `services/learning_service.py::_load_points` 重复了相同的知识点 JSON 解析逻辑；已删除服务端未使用的 `_load_points`（提交 `73ea445`）。
- **Spec**：两处与设计稿的偏差已在 `73ea445` 修复——「开始检验」移到页面顶部（返回链接旁）；左侧状态栏补回「当前教学阶段」。其余 spec 需求（入口、恢复、幂等、最近 12 轮上下文、稳定 502、安全 Markdown、检验唯一完成通道）均有测试覆盖。

## 环境与已知警告

- 为规避本机系统临时目录权限问题，`backend/tests/conftest.py` 将 pytest `tmp_path` 根指向项目内 `.pytest_tmp/`（已加入 `.gitignore`）。
- 非阻塞警告：Starlette `TestClient` 弃用提示；`TestContent` Pydantic 类触发 pytest 收集提示；React Router v6 future flag 提示；Git LF/CRLF 换行提示。

## 冒烟与评审状态

- 手动冒烟（真实 DeepSeek 调用 + 真实 `learn` 任务）未在本环境执行：需要配置 `DEEPSEEK_API_KEY` 并能访问 DeepSeek API，建议按计划 Task 7 的清单在用户环境完成。
- 独立代码评审已按计划要求执行（从设计提交 `026b77e` 至当前 HEAD 的双轴评审），Critical/Important 发现已在 `73ea445` 修复；评审范围同时覆盖了分支上的时长排程与 UI 改动，未发现需要另行处理的阻断项。
