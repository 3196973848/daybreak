# Daybreak

> 把一个目标，变成每天的日程

目标驱动的规划 Web 应用：输入一个目标和每日投入时间，AI 拆解成里程碑和每日任务，排程算法排出日程，支持勾选完成、AI 导师学习、检验验证。

## ✨ 核心功能

### 🎯 智能计划生成
- 输入目标 + 每日投入时间，AI 自动生成学习计划
- 预览模式：查看策略、假设清单、里程碑大纲
- 支持否决不适用的假设，计划据此调整

### 📅 灵活日程管理
- **连续安排**：任务填满每个工作日，不跳天空闲
- **休息日**：创建计划时选择每周休息日
- **请假**：每日任务页面支持请假日，任务自动后延
- **重排**：一键重新安排未完成任务，支持调整每日时长

### 📊 进度追踪
- **容量校准**：记录实际用时，对比预计 vs 实际
- **节奏建议**：偏差超过 30% 自动提示调整
- **周复盘**：每周完成率、用时、检验通过率统计

### 🎓 学习验证
- AI 导师：诊断 → 讲解 → 练习 → 检验的学习流程
- 10 道检验题（7 选择 + 3 简答），70 分及格
- 错题自动生成补强任务

### 📆 日历订阅
- iCal 订阅链接，支持系统日历自动同步
- 任务完成状态实时更新

## 🚀 快速开始

### 后端
```bash
cd backend
pip install -r requirements.txt

# 配置 LLM API Key（选择一个）
export DEEPSEEK_API_KEY=sk-...    # DeepSeek（推荐）
# export OPENAI_API_KEY=sk-...    # OpenAI
# export ANTHROPIC_API_KEY=sk-ant-...  # Claude

# 启动
uvicorn app.main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### 桌面版（带提醒）
```bash
cd backend
python run_desktop.py
```

## 🧪 测试
```bash
cd backend && python -m pytest -v
```

222 个测试，覆盖全部功能。

## 📁 项目结构

```
backend/
├── app/
│   ├── api/           # REST API 路由
│   │   ├── goals.py   # 目标管理（创建、重排、预览、请假、复盘）
│   │   ├── tasks.py   # 任务管理（完成、验证、补强）
│   │   ├── settings.py # 设置（LLM Provider 配置）
│   │   ├── auth.py    # 认证（登录、注册）
│   │   └── learning.py # AI 导师学习
│   ├── llm/           # LLM 集成
│   │   ├── planner.py # 计划生成
│   │   ├── verifier.py # 检验出题/评分
│   │   ├── tutor.py   # AI 导师
│   │   └── client.py  # LLM 客户端
│   ├── scheduler/     # 排程算法
│   │   ├── scheduler.py # 核心调度（支持休息日、请假）
│   │   └── duration.py  # 时长计算
│   ├── services/      # 业务服务
│   │   ├── planner_service.py # 计划生成 + 重排
│   │   ├── capacity.py        # 容量检查
│   │   └── learning_service.py # 学习服务
│   └── models.py      # 数据模型
└── tests/             # 测试

frontend/
└── src/
    ├── pages/
    │   ├── GoalInput.tsx     # 首页（目标输入 + 预览）
    │   ├── PlanOverview.tsx  # 计划总览（重排、复盘入口）
    │   ├── DailyTasks.tsx    # 每日任务（请假、完成）
    │   ├── ReviewPage.tsx    # 周复盘
    │   ├── LearningPage.tsx  # AI 导师学习
    │   └── SetupPage.tsx     # 设置（LLM Provider）
    ├── components/           # 通用组件
    └── api/client.ts         # API 客户端
```

## 🔌 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/goals` | POST | 创建目标（生成计划） |
| `/api/goals/preview` | POST | 预览计划（不写库） |
| `/api/goals/{id}/replan` | POST | 增量重排 |
| `/api/goals/{id}/pace` | GET | 容量校准统计 |
| `/api/goals/{id}/review` | GET | 周复盘统计 |
| `/api/goals/{id}/leave` | POST | 请假 |
| `/api/goals/{id}/leave/{date}` | DELETE | 取消请假 |
| `/api/goals/{id}/calendar.ics` | GET | iCal 订阅 |
| `/api/tasks/{id}` | PATCH | 完成/取消任务 |
| `/api/tasks/{id}/verification` | GET/POST | 检验 |
| `/api/tasks/{id}/learning-session` | GET/POST | AI 导师 |
| `/api/settings` | GET/POST | LLM 设置 |
| `/api/settings/providers` | POST | 添加自定义 Provider |

## 🤖 支持的 LLM

| Provider | 模型 | 需要 API Key |
|----------|------|-------------|
| DeepSeek | deepseek-v4-pro, deepseek-chat | ✅ |
| OpenAI | gpt-4o-mini, gpt-4o | ✅ |
| Claude | claude-sonnet-4 | ✅ |
| Ollama | qwen2.5, llama3.1 | ❌（本地运行） |
| 自定义 | 任意 OpenAI 兼容 | 可选 |

## 📄 许可证

MIT License
