# Daybreak 项目交接文档

> 最后更新：2026-08-20
> 版本：v2.0.0

---

## 一、项目概述

**Daybreak** 是一个目标驱动的规划 Web 应用。用户输入一个目标和每日投入时间，AI 自动拆解成里程碑和每日任务，排程算法排出日程，用户按日执行并验证学习成果。

**核心理念**：把"从想法到计划"做得又快又好，让静态计划变成可执行的每日行动。

**技术栈**：
- 后端：Python 3.10 + FastAPI + SQLAlchemy + SQLite
- 前端：React 18 + TypeScript + Vite + react-router-dom
- LLM：DeepSeek / OpenAI / Ollama / Claude（可切换）

**仓库**：https://github.com/3196973848/daybreak

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│   SQLite    │
│  React/Vite │◀────│   FastAPI   │◀────│  Database   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │    LLM API  │
                    │ DeepSeek 等 │
                    └─────────────┘
```

### 2.2 数据模型

```
User (用户)
  └── Goal (目标)
        └── Plan (计划)
              └── Milestone (里程碑)
                    └── Task (任务)
                          └── VerificationRecord (检验记录)
                          └── LearningSession (学习会话)
                                └── LearningTurn (对话轮次)
```

**核心模型字段**：

| 模型 | 关键字段 |
|------|----------|
| User | id, username, password_hash |
| Goal | id, user_id, title, description, target_date, feed_token, leave_dates |
| Plan | id, goal_id, strategy, status |
| Milestone | id, plan_id, title, order, due_date, status |
| Task | id, milestone_id, title, type, scheduled_date, effort, actual_minutes, status, verified |
| VerificationRecord | id, task_id, mode, content, submission, result, passed |

### 2.3 调度算法

**核心逻辑**（`scheduler/scheduler.py`）：
- 任务按里程碑顺序排列
- 每个任务需要 `ceil(effort_hours / hours_per_block)` 个时间块
- 任务填满每个工作日（连续安排，不跳天）
- 支持 `rest_days`（每周休息日）和 `skip_dates`（请假日期）
- 容量不足时自动延长截止日期

**关键函数**：
```python
def schedule(plan, start_date, ..., rest_days=None, skip_dates=None) -> list[ScheduledTask]
def group_tasks(plan, daily_hours) -> list[list[tuple[int, int]]]
```

---

## 三、功能模块

### 3.1 目标创建与计划生成

**流程**：
1. 用户输入：目标标题 + 每日投入时间 + 休息日（可选）
2. 预览：AI 生成策略、假设清单、里程碑大纲
3. 用户可否决不适用的假设
4. 确认生成：LLM 生成完整计划 → 调度器排程 → 写入数据库

**关键文件**：
- `api/goals.py` → `POST /api/goals/preview`, `POST /api/goals`
- `services/planner_service.py` → `create_goal_with_plan()`
- `llm/planner.py` → `generate_plan()`, `generate_preview()`

### 3.2 增量重排（Replan）

**场景**：用户错过几天后，未完成任务堆积

**流程**：
1. 已完成任务保持不动
2. 未完成任务从今天起重新调度
3. 支持调整每日时长和休息日
4. 容量不足时自动延长截止日期

**API**：`POST /api/goals/{id}/replan`

**关键逻辑**：
```python
def replan_goal(db, goal_id, user_id, daily_hours=None, rest_days=None):
    # 收集未完成任务
    # 构建虚拟 PlanSpec
    # 调度并更新日期
    # 更新 target_date
```

### 3.3 容量校准（Pace）

**目的**：让系统知道预算准不准

**数据**：
- `Task.actual_minutes`：完成时可选填写实际耗时
- `GET /api/goals/{id}/pace`：返回预计 vs 实际对照

**返回示例**：
```json
{
  "total_tasks": 10,
  "completed_tasks": 5,
  "planned_hours": 10.0,
  "actual_hours": 12.5,
  "deviation_pct": 25.0,
  "suggestion": { "type": "increase_budget", "message": "..." }
}
```

### 3.4 生成前澄清（Preview）

**目的**：消灭 LLM 的沉默假设

**流程**：
1. `POST /api/goals/preview` 生成预览
2. 返回 `assumptions: string[]`（3-5 条假设）
3. 用户可否决假设
4. 否决的假设作为 feedback 传入正式生成

### 3.5 iCal 订阅

**实现**：
- Goal 生成时自动创建 `feed_token`
- `GET /api/goals/{id}/calendar.ics?token=...` 免登录访问
- 任务完成 → `STATUS:COMPLETED`
- 重排后日期自动反映

### 3.6 周复盘（Review）

**API**：`GET /api/goals/{id}/review?week=YYYY-WW`

**返回**：
- 每日任务数 / 完成数 / 实际耗时
- 检验通过率
- 自动生成结论（优秀/良好/一般/需调整）

### 3.7 错题回流（Remedy）

**流程**：
1. 检验不通过（<70 分）
2. 调用 `generate_remedy_tasks()` 生成 1-2 个补强任务
3. 补强任务自动安排到最近可用日
4. 再次检验不出原题

### 3.8 请假功能

**API**：
- `POST /api/goals/{id}/leave` → 请假，任务后延
- `DELETE /api/goals/{id}/leave/{date}` → 取消请假，任务恢复

**逻辑**：
- 请假日及之后的任务 +1 天
- 取消请假日之后的任务 -1 天
- `Goal.leave_dates` 存储请假日期列表

### 3.9 桌面提醒

**实现**：
- `app/reminder.py`：定时检查今日任务
- 支持 Windows/macOS/Linux 系统通知
- `run_desktop.py` 启动时自动启动提醒

### 3.10 认证系统

**实现**：
- `app/auth.py`：JWT Token 认证
- 支持登录/注册
- `auth_enabled` 配置开关

---

## 四、LLM 集成

### 4.1 Provider 配置

**内置 Provider**：
- DeepSeek（推荐）
- OpenAI
- Ollama（本地）
- Claude

**自定义 Provider**：
- `POST /api/settings/providers` 添加
- `DELETE /api/settings/providers/{id}` 删除
- 存储在 `planagent.conf` 的 `PLANAGENT_CUSTOM_PROVIDERS` 字段

### 4.2 LLM 调用

**客户端**：`llm/client.py` → `chat()` 函数
- 自动处理 JSON 输出格式
- 支持流式输出
- 错误重试

**计划生成**：`llm/planner.py`
- `generate_plan()`：生成完整计划
- `generate_preview()`：生成预览
- Prompt 包含任务类型、工时范围、假设要求

**检验**：`llm/verifier.py`
- `generate_test()`：生成 10 道题
- `grade_test()` / `score_test()`：评分
- `generate_remedy_tasks()`：生成补强任务

### 4.3 关键设计决策

**LLM 只出内容，日期/计分一律服务端算**：
- LLM 生成任务和工时，但不生成日期
- 日期由调度器根据用户设置计算
- 检验评分由服务端逻辑判定

**Pydantic 校验 + 反馈重试**：
- LLM 输出必须通过 Pydantic 模型校验
- 校验失败时自动重试（最多 3 次）
- 失败原因作为 feedback 传入下一次调用

---

## 五、前端架构

### 5.1 页面结构

```
/                     → GoalInput（首页）
/goals/:id            → PlanOverview（计划总览）
/goals/:id/daily      → DailyTasks（每日任务）
/goals/:id/review     → ReviewPage（周复盘）
/tasks/:taskId/learn  → LearningPage（AI 导师）
/setup                → SetupPage（设置）
```

### 5.2 状态管理

- React hooks（useState, useEffect, useMemo）
- 无全局状态管理库
- API 调用通过 `api/client.ts` 封装

### 5.3 国际化

- `i18n.ts`：中英文切换
- `useI18n()` hook
- 翻译键值对

### 5.4 认证

- `auth/AuthContext.tsx`：用户状态
- `auth/SetupGate.tsx`：首次使用引导

---

## 六、配置

### 6.1 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PLANAGENT_LLM_PROVIDER` | LLM 提供商 | deepseek |
| `PLANAGENT_LLM_MODEL` | 模型名称 | deepseek-v4-pro |
| `PLANAGENT_LLM_API_KEY` | API Key | - |
| `PLANAGENT_LLM_BASE_URL` | API 地址 | https://api.deepseek.com |
| `PLANAGENT_AUTH_ENABLED` | 启用认证 | false |
| `PLANAGENT_BLOCKS_PER_DAY` | 每日时间块 | 2 |
| `PLANAGENT_HOURS_PER_BLOCK` | 每块小时数 | 1.0 |

### 6.2 配置文件

**位置**：`backend/planagent.conf`

**格式**：
```
PLANAGENT_LLM_PROVIDER=deepseek
PLANAGENT_LLM_MODEL=deepseek-chat
PLANAGENT_LLM_API_KEY=sk-...
PLANAGENT_LLM_BASE_URL=https://api.deepseek.com
```

---

## 七、API 端点完整列表

### 7.1 目标管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/goals/preview` | 预览计划 |
| POST | `/api/goals` | 创建目标 |
| GET | `/api/goals` | 列出所有目标 |
| GET | `/api/goals/{id}` | 获取目标详情 |
| DELETE | `/api/goals/{id}` | 删除目标 |
| POST | `/api/goals/{id}/replan` | 增量重排 |
| GET | `/api/goals/{id}/pace` | 容量校准 |
| GET | `/api/goals/{id}/review` | 周复盘 |
| POST | `/api/goals/{id}/leave` | 请假 |
| DELETE | `/api/goals/{id}/leave/{date}` | 取消请假 |
| GET | `/api/goals/{id}/calendar.ics` | iCal 订阅 |

### 7.2 任务管理

| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/api/tasks/{id}` | 完成/取消任务 |
| GET | `/api/tasks/{id}/verification` | 开始检验 |
| POST | `/api/tasks/{id}/verification` | 提交检验 |
| GET | `/api/tasks/{id}/learning-session` | 获取学习会话 |
| POST | `/api/tasks/{id}/learning-session` | 开始学习 |
| POST | `/api/tasks/{id}/learning-session/turns` | 发送学习消息 |

### 7.3 设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取设置 |
| POST | `/api/settings` | 保存设置 |
| GET | `/api/settings/models` | 获取可用模型 |
| POST | `/api/settings/providers` | 添加自定义 Provider |
| DELETE | `/api/settings/providers/{id}` | 删除自定义 Provider |

### 7.4 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前用户 |

---

## 八、测试

### 8.1 测试结构

```
backend/tests/
├── conftest.py              # 测试配置（内存数据库、认证 mock）
├── test_goals_api.py        # 目标 API 测试
├── test_tasks_api.py        # 任务 API 测试
├── test_optimizations.py    # 优化功能测试（replan, pace, review, remedy）
├── test_planner_service.py  # 计划服务测试
├── test_scheduler.py        # 调度器测试
├── test_verifier.py         # 检验器测试
├── test_settings_api.py     # 设置 API 测试
└── ...
```

### 8.2 运行测试

```bash
cd backend && python -m pytest -v
```

**当前状态**：222 passed, 5 failed（预先存在的问题）

---

## 九、部署

### 9.1 开发环境

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

### 9.2 生产环境

```bash
# 构建前端
cd frontend && npm run build

# 启动后端
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 9.3 桌面版

```bash
cd backend && python run_desktop.py
```

---

## 十、设计思路与决策记录

### 10.1 为什么用 SQLite？

- 本地单用户场景，无需外部数据库
- 零配置，开箱即用
- 文件级备份，便于迁移

### 10.2 为什么调度器不用 LLM？

- 调度是确定性问题，不需要 AI
- 保证可预测性和可测试性
- LLM 只负责内容生成，日期由服务端计算

### 10.3 为什么需要假设清单？

- LLM 会做隐式假设（如"用户已掌握基础语法"）
- 这些假设可能不适用于特定用户
- 让用户审阅假设可以提高计划质量

### 10.4 为什么任务连续安排？

- 用户反馈"日程过于松散"
- 每天都有任务可以保持学习节奏
- 休息日由用户主动选择，而不是系统默认跳天

### 10.5 为什么容量不足时自动延长？

- 原来的 InsufficientCapacityError 会阻断用户流程
- 用户不关心技术细节，只想完成目标
- 自动延长截止日期更符合用户期望

---

## 十一、已知问题

1. **测试兼容性**：部分旧测试在新版本下失败（5 个）
2. **网络依赖**：LLM 调用需要网络，离线不可用
3. **数据库迁移**：新增字段需要手动 ALTER TABLE

---

## 十二、后续优化方向

1. **领域感知**：支持健身、习惯等非学习类目标
2. **多模态任务**：支持组数、次数等度量单位
3. **移动端适配**：响应式设计优化
4. **数据导出**：支持导出为 CSV/JSON
5. **协作功能**：多人共享目标

---

## 十三、关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/models.py` | 数据模型定义 |
| `backend/app/api/goals.py` | 目标 API（最核心） |
| `backend/app/api/tasks.py` | 任务 API |
| `backend/app/services/planner_service.py` | 计划生成 + 重排 |
| `backend/app/scheduler/scheduler.py` | 调度算法 |
| `backend/app/llm/planner.py` | LLM 计划生成 |
| `backend/app/llm/verifier.py` | LLM 检验 |
| `backend/app/config.py` | 配置管理 |
| `frontend/src/pages/GoalInput.tsx` | 首页 |
| `frontend/src/pages/PlanOverview.tsx` | 计划总览 |
| `frontend/src/pages/DailyTasks.tsx` | 每日任务 |
| `frontend/src/api/client.ts` | API 客户端 |

---

**文档结束**
