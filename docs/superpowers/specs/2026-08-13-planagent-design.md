# PlanAgent 设计文档

日期:2026-08-13
状态:待审阅

## 1. 概述

PlanAgent 是一个**目标驱动的规划 Web 应用**:用户输入一个目标,应用通过 LLM 把目标拆解成阶段性的小目标(里程碑),再细分成每日任务,产出合理的日程安排。用户可以在界面上追踪每日任务的完成情况,查看整体进度。

核心价值:**把模糊的大目标变成清晰、可执行、排好日期的每日行动计划**。

### 范围

- **MVP 范围**:单用户本地;静态计划生成 + 完成度追踪(不做动态重规划)
- **后续迭代**(不在 MVP):动态自适应重规划、多用户账号、日历导入导出、提醒通知

## 2. 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 目标领域 | 通用目标规划 | 任何目标(学习/健身/副业等),由 LLM 理解拆解 |
| 交付形态 | Web 应用 | 有界面交互,适合展示计划与追踪进度 |
| 智能核心 | LLM 驱动(DeepSeek,OpenAI 兼容接口) | 处理任意目标,JSON 模式 + 服务端 Pydantic 校验 |
| 进度追踪 | 静态计划 + 完成度追踪 | MVP 简化,动态重规划放后续 |
| 用户体系 | 单用户本地 | 无登录,SQLite 存储,架构最简 |
| 技术栈 | Python (FastAPI) + React (Vite) + SQLite | 前后端分离,LLM 生态 Python 最佳,模块边界清晰 |

## 3. 架构

两个独立进程,前后端分离,通过 REST API 通信。

```
planagent/
├── backend/            FastAPI 服务器 (:8000)
│   ├── llm/            LLM 编排(调 DeepSeek API,JSON 输出 + 服务端校验)
│   ├── scheduler/      排程算法(把任务排到具体日期)
│   ├── models/         数据模型
│   ├── storage/        SQLite 读写
│   └── api/            REST 路由
├── frontend/           React + Vite SPA (:5173, 开发代理到 :8000)
└── docs/specs/         设计文档
```

### 数据流

1. 用户在目标输入页提交目标
2. 后端调用 LLM,产出结构化规划(策略 + 里程碑 + 任务 + 预估工时)
3. 排程算法把任务排到具体日期,生成完整日程
4. 前端展示计划总览和每日视图
5. 用户勾选任务完成 → 前端调 PATCH API → 后端更新状态 → 进度自动重算

## 4. 数据模型

```
Goal(id, title, description?, target_date?, created_at)
  └── Plan(id, goal_id, strategy, status, generated_at)      # 1 goal → 1 plan
        └── Milestone(id, plan_id, title, description, order, due_date, status)
              └── Task(id, milestone_id, title, description, type, scheduled_date,
                       effort, order, status, verified, completed_at)
                    └── VerificationRecord(id, task_id, mode, content, submission,
                                           result, passed, created_at)   # 0..N, 检验历史
```

| 实体 | 字段 | 说明 |
|---|---|---|
| Goal | title, description?, target_date? | 用户目标;target_date 可选(LLM 会据此约束计划时长) |
| Plan | strategy, status | 策略摘要文本;status = generating / active / archived |
| Milestone | title, description, order, due_date, status | 阶段性小目标;status = todo / active / done |
| Task | title, description, type, scheduled_date, effort, order, status, verified, completed_at | 每日任务;type = learn / practice / project;status = todo / done;verified = 是否检验通过 |
| VerificationRecord | mode, content, submission, result, passed, created_at | 单次检验记录;mode = test / deliver;保留检验历史 |

关系:Goal → 1 Plan → N Milestone → N Task。Task 挂在 milestone 下,但排期独立由调度算法分配。VerificationRecord 挂在 task 下,记录每次检验。

### 状态与进度

- Milestone 状态:全部 task 完成 → done;有任一进行中 → active;否则 todo
- 计划总进度 = 已完成 task 数 / 总 task 数
- 前端进度条、里程碑徽章由此计算
- Task 有三种终态表现:未完成 / 自行完成(勾选,无验证)/ 已验证(检验通过)

## 5. LLM 编排

### 职责分离(核心设计决策)

- **LLM 只负责"是什么"**:目标拆解、里程碑设计、任务内容、预估工时,不负责"哪天做"
- **排程算法负责"哪天做"**:确定性算法,把任务铺到日历上

这个分离带来三点好处:排程可单元测试(相同 LLM 输出 → 相同日程);LLM 不会产出自相矛盾的日期;排程逻辑可独立调整(如每天容量)。

### 一次调用,结构化输出

```
POST /api/goals
→ LLM(goal 信息) → 结构化 JSON:
{
  strategy: string,
  milestones: [
    {
      title, description, order,
      target_date_offset_days: int,          # 相对计划起始日
      tasks: [
        { title, description, type, effort_hours: number }   # type = learn / practice / project
      ]
    }
  ]
}
```

- 用 DeepSeek 的 JSON 模式(`response_format=json_object`),服务端 Pydantic 校验保证可解析
- 校验通过后交给排程算法;校验失败自动重试一次(换提示词),仍失败返回明确错误

### 排程算法(MVP 规则)

- 每天默认 2 个时间块(可配置),一个任务占一个或多个块(按 effort_hours)
- 任务按 order 串行铺入里程碑时间窗;超过则顺延
- 输出每个 task 的 scheduled_date

### 任务检验(可选增强)

检验是**可选**机制:任务可自行勾选完成,也可送检;检验通过后获得"已验证"标记。所有任务类型都可送检,**检验方式由 agent 按任务类型自行选择**:

- **测试(test)** —— 学习类任务(learn):agent 基于任务内容实时出题(选择题 + 简答题),用户在检验区作答,agent 判分。正确率 ≥70% 判通过
- **交付评审(deliver)** —— 实操/项目类任务(practice/project):用户提交交付物描述(成果/代码/链接等),agent 对照任务验收标准评审是否达标

每次检验的流程:获取检验内容(测试→题目;交付→要求) → 用户提交(作答/交付描述) → agent 判分/评审 → 通过则标记 verified → 记录到 VerificationRecord。检验方式、内容、提交、结果都存档,保留历史,可重新检验(每次实时生成)。

### 错误处理(LLM 层)

- API 调用失败/超时 → 返回可重试错误给前端
- 结构化输出解析失败 → 自动重试一次(换提示词)→ 仍失败返回明确错误("生成失败,请重试")

## 6. REST API

```
POST   /api/goals           创建目标 → 触发 LLM 生成 → 返回完整计划(同步等待,几秒)
GET    /api/goals           目标列表
GET    /api/goals/{id}      单个目标 + 计划 + 里程碑 + 任务
PATCH  /api/tasks/{id}      勾选完成/取消完成 { completed: true/false }
GET    /api/tasks/{id}/verification      获取检验内容(测试→题目;交付→要求)
POST   /api/tasks/{id}/verification      提交(作答/交付描述) → 判分/评审 → 通过则标记 verified
DELETE /api/goals/{id}      删除目标
GET    /api/health          健康检查
```

- `POST /api/goals` 同步等待 LLM 生成(MVP 不做异步任务队列,简单可靠)
- 前端拿到的就是最终排好的日程(带 scheduled_date),不需要自己算日期
- 检验端点为可选流程:出题/评审调用失败 → 提示重试,不影响任务本身状态

## 7. 前端设计

### 技术栈

React + Vite + TypeScript + 轻量数据请求(React Query 或类似),不引入重型全局状态库。

### 配色(黑灰主题,经可视化确认)

| 用途 | 色值 |
|---|---|
| 页面背景 | `#000000` |
| 卡片背景 | `#1a1a1a` |
| 卡片边框 | `#2e2e2e` |
| 强调(进度条/勾选/主按钮) | `#e5e5e5`(白) |
| 主文字 | `#e5e5e5` |
| 次要文字 | `#a3a3a3` |
| 弱化文字 | `#737373` |
| 完成状态 | 灰 `#737373` + 删除线 |

无彩色强调,纯黑 + 灰阶 + 白色。

### 页面与布局(经可视化确认)

**视图 1 · 目标输入页**
- 输入:目标标题(必填)、补充说明(可选)、目标完成日期(可选)
- "生成计划"按钮(白色实底黑字);生成中显示 loading 并禁用
- 提示文案:生成需要几秒

**视图 2 · 计划总览页**
- 顶部:目标标题 + 整体进度条(已/总任务数)+ 策略摘要
- 里程碑卡片时间线:每个卡片含标题、阶段说明、日期范围、状态徽章(进行中/已完成/未开始,灰阶区分)
- 可展开里程碑查看其任务列表

**视图 3 · 每日任务页(左右布局)**
- 左侧:任务列表 —— 日期切换(‹ 日期 ›)、任务勾选圆点(白底勾)、完成的任务灰 + 删除线、每任务显示预估时长、今日完成统计;任务行显示"去检验"按钮
- 右侧:月历面板 —— 有任务的日子显示白点标记;今天有边框;选中日期白底黑字高亮;点击任意日期左侧切换为该日任务

**视图 4 · 检验区(弹窗/抽屉)**
- 从任务行"去检验"进入;检验方式由 agent 按任务类型决定
- **测试模式**:显示实时生成的题目(选择题 + 简答题),用户作答提交后显示判分结果;通过显示"已验证"标记
- **交付模式**:显示交付要求,用户填写交付物描述提交,agent 评审后显示是否达标
- 检验历史可在弹窗内查看(每次提交的结果记录)

### 交互要点

- 勾选任务 → PATCH /api/tasks/{id} → 后端更新 → 前端本地回滚(失败时)
- 任务勾选后,可通过"去检验"提交验证;验证通过标记"已验证"(与自行完成的样式区分)
- 检验区出题/评审为异步调用,提交期间显示 loading;失败 toast 提示重试,不影响任务状态
- API 错误统一 toast 提示
- 生成计划 loading 态禁用按钮

## 8. 错误处理与健壮性

分层处理:
- **LLM 层**:如上文 §5,失败重试,明确报错
- **排程层**:纯函数,合法输入 → 合法输出;非法输入(空任务列表)提前校验返回 400
- **前端**:API 错误 toast;生成中 loading;勾选失败回滚

## 9. 测试策略

- **后端单元测试**:scheduler(纯函数,给固定 LLM 输出断言日期)、LLM 输出校验、storage
- **后端集成测试**:FastAPI TestClient + mock LLM(固定返回)走完整流程,包括检验流程(出题 → 提交 → 判分/评审 → 标记 verified → 记录 VerificationRecord)
- **前端**:组件冒烟测试(可选 MVP);重点手工验证三视图

## 10. 开发流程

- monorepo:backend/ + frontend/,各自独立 requirements.txt / package.json
- 后端 `uvicorn` 起在 :8000;前端 `vite dev` 起在 :5173 并代理到 :8000
- LLM 走 DeepSeek(OpenAI 兼容接口),模型 `deepseek-v4pro`,key 用环境变量 `DEEPSEEK_API_KEY`(config 经 `PLANAGENT_LLM_API_KEY` 读取)
- `.superpowers/` 加入 .gitignore

## 11. 后续迭代(不在 MVP)

- 动态自适应重规划(落后自动重新排期)
- 多用户账号
- 日历导入导出(iCal)
- 提醒通知
