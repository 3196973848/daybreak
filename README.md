# PlanAgent

目标驱动的规划 Web 应用：输入一个目标，AI 拆解成里程碑和每日任务，排程算法排出日程，支持勾选完成与「去检验」验证。

## 运行

### 后端
```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (已代理 /api 到 :8000)
```

## 测试
```bash
cd backend && python -m pytest
```

## 结构
- `backend/app/llm` — LLM 编排(计划生成、检验出题/判分)
- `backend/app/scheduler` — 确定性排程算法
- `backend/app/services` — 计划生成服务(LLM+排程+落库)
- `backend/app/api` — REST 路由
- `frontend/src` — React 前端
