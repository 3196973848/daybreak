# PlanAgent

目标驱动的规划 Web 应用：输入一个目标，AI 拆解成里程碑和每日任务，排程算法排出日程，支持勾选完成与「去检验」验证。

## 排程规则

创建目标时输入正整数预期时长，并选择天、周或月。服务端以创建当天为开始日，计算并保存目标截止日期，再按任务顺序把计划均匀铺到整个自然日区间；周末也会安排任务。首个任务安排在当天，最后一个任务不晚于截止日。

创建目标时还可填写每日可投入时间，默认 2 小时。AI 会自行识别目标涉及的领域，把宽泛内容拆成以 0.5 小时为粒度的具体子任务；每天的任务数量可以不同，但累计预计耗时不会超过每日预算。任务组仍会包含周末地均匀铺满整个预期周期。若周期容量不足，系统不会创建计划，而会显示所需小时数和建议的最短天数。

学习任务的每次检验会重新生成 10 道题（7 道选择题、3 道简答题）。每题 10 分：选择题由服务端按正确答案计分，简答题由 AI 按评分点逐题计分；总分达到 70 分即通过。

`POST /api/goals` 使用 `duration_value` 与 `duration_unit`（`day` / `week` / `month`）。旧客户端仍可提交 `target_date`；未提供任何期限时保留按每日容量尽快安排的行为。

## 运行

### 后端
```bash
cd backend
pip install -r requirements.txt
export DEEPSEEK_API_KEY=sk-...
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
