# Daybreak 优化任务书

> 基于 project-loop 五阶段闭环框架（澄清 CLARIFY → 设计 DESIGN → 执行 BUILD → 交付 DELIVER → 复盘 REFLECT）对 daybreak 产品闭环的分析结论。
> 核心判断：**daybreak 把"从想法到计划"做得又快又好，但计划生成后系统不再学习——静态计划无法应对"计划赶不上变化"。**
> 按优先级排列，每个任务独立可交付，附完成标准。建议按 P0 → P3 顺序执行。

## 现状诊断总览

| 闭环阶段 | 覆盖度 | 现状 |
|---|---|---|
| 澄清环 | 30% | 一句话目标 + 时长 + 每日预算，三参数直出全量计划，关键决策全靠 LLM 隐式假设 |
| 设计环 | 50% | 原子校验/容量检查/重试反馈做得好；但计划无用户审阅门禁，均匀排程是静态假设 |
| 执行环 | 85% | 全产品最强：日历、勾选、流式导师、持久化对话、防重复出题 |
| 交付环 | 55% | 检验体系完整（10 题 70 分、服务端计分、交付评审）；但无提醒机制，iCal 一次性导出不同步 |
| 反馈环 | 15% | VerificationRecord 存了完整历史但无消费者；无 replan API；实际耗时不回收 |

---

## P0-1 增量重排（replan）——把静态计划变成活的

**问题**：`api/tasks.py` 只有 `PATCH /{task_id}`（勾选完成）和 verification 两组端点，没有任何重排入口。用户错过几天任务后欠账累积，计划与日历脱节，只能删掉重建——这是工具类产品最典型的弃用路径。

**方案**：
1. 新增 `POST /api/goals/{goal_id}/replan`：
   - 已完成的任务与已通过的检验保持不动
   - 未完成任务从"今天"起重新计算剩余工作量，按现有 `group_tasks` + `schedule` 逻辑增量重排
   - 若剩余容量不足，返回与创建时相同的 `InsufficientCapacityError` 结构（所需小时数 + 建议最短天数），由用户决定延期或砍范围
2. 前端 PlanOverview 页加"重新安排未完成任务"按钮，展示重排预览（哪些任务会移动到哪天）后确认执行
3. 重排记录写入日志（可选：复用 VerificationRecord 或新增字段记录 replan 次数）

**涉及文件**：`backend/app/api/goals.py`、`backend/app/services/planner_service.py`、`backend/app/scheduler/scheduler.py`、`frontend/src/pages/PlanOverview.tsx`

**完成标准**：
- [ ] 错过 N 天后调用 replan，已完成任务日期不变，未完成任务从今天起重新铺排且不晚于（必要时自动顺延的）截止日
- [ ] 容量不足时返回结构化错误而非 500
- [ ] pytest 覆盖：部分完成 / 全部未完成 / 容量不足三种场景
- [ ] 前端可触发重排并看到结果

## P0-2 容量校准——让系统知道预算准不准

**问题**：`daily_hours` 默认 2 小时，创建后永不更新。用户天天超时或天天提前完成，系统毫无感知，排程精度随时间衰减。

**方案**：
1. 任务模型加 `actual_minutes` 字段（可空），勾选完成时可选填写实际耗时（前端在完成弹窗里加一个可选输入）
2. 新增统计端点 `GET /api/goals/{goal_id}/pace`：返回预计 vs 实际的日均对照、偏差百分比、按当前真实速度推算的完成日
3. 偏差超过 ±30% 时，在 PlanOverview 顶部给一条建议条："按你的实际节奏，建议将每日预算调为 X 小时 / 将期限延至 Y 日"，一键应用（应用即触发 P0-1 的 replan）

**涉及文件**：`backend/app/models.py`、`backend/app/api/tasks.py`、`backend/app/api/goals.py`、`frontend/src/pages/PlanOverview.tsx`

**完成标准**：
- [ ] 记录了实际耗时的任务参与 pace 计算，未记录的按预计值兜底
- [ ] pace 端点返回预计/实际对照与推算完成日
- [ ] 偏差阈值触发的建议可一键应用到重排
- [ ] pytest 覆盖 pace 计算的边界（无记录、部分记录、全部记录）

## P1-1 生成前澄清——消灭沉默假设

**问题**：tutor 有"诊断"环节但发生在任务级、计划生成之后，顺序反了。计划建在 LLM 对用户水平的猜测上。

**方案**（低成本版，不引入多轮对话复杂度）：
1. `generate_plan` 的 prompt 要求 LLM 在计划 JSON 里附带 `assumptions: string[]` 字段（3-5 条，如"假设你已掌握基础语法""假设工作日每天可投入 2 小时"）
2. 创建目标 API 改为两段式（保持向后兼容）：
   - `POST /api/goals/preview`：只生成里程碑大纲 + 假设清单，不排程不入库
   - 用户在前端确认/逐条否决假设、可编辑里程碑标题后，`POST /api/goals` 携带修正信息正式生成
3. 被否决的假设转成 feedback 传入 `generate_plan` 的重试循环（该机制已存在，直接复用）

**涉及文件**：`backend/app/llm/planner.py`、`backend/app/llm/schema.py`、`backend/app/api/goals.py`、`frontend/src/pages/GoalInput.tsx`

**完成标准**：
- [ ] preview 端点返回大纲 + 假设清单，不写库
- [ ] 假设可被否决且否决信息影响最终计划（pytest 验证 feedback 传入）
- [ ] 旧的直接创建路径保持可用（旧客户端不破坏）

## P1-2 iCal 订阅 feed——导出一次变成持续同步

**问题**：`GET /api/goals/{goal_id}/calendar.ics` 是一次性导出，replan 或勾选后系统日历里的旧事件全部作废。

**方案**：
1. 给每个 goal 生成不可猜测的 `feed_token`（secrets.token_urlsafe）
2. 现有 ics 端点支持 `GET /api/goals/{goal_id}/calendar.ics?token=...` 免登录访问（本地单用户场景，token 即鉴权）
3. ics 响应头加 `Content-Disposition: inline`，用户在系统日历里添加"日历订阅"URL 即可自动刷新
4. 事件状态联动：任务完成时对应 VEVENT 加 `STATUS:COMPLETED`；replan 后日期自动反映在下次拉取

**涉及文件**：`backend/app/models.py`、`backend/app/api/goals.py`

**完成标准**：
- [ ] 带 token 的 URL 免登录可访问，无 token/错 token 返回 401
- [ ] 勾选完成后 ics 中对应事件标记完成
- [ ] replan 后 ics 反映新日期
- [ ] pytest 覆盖 token 校验与 ics 内容

## P1-3 桌面提醒——每日行动应用不能靠用户记得打开

**问题**：产品核心承诺是"每一天都有下一步"，但没有任何提醒机制。

**方案**（桌面版，按现有 pywebview/pystray 或系统通知能力选型）：
1. 后端 `run_desktop.py` 起一个轻量定时器：每天固定时间（默认早 8 点，设置页可改）检查"今天有任务的所有 goal"
2. 有任务则发系统通知："今天有 N 个任务，第一个是 XXX（预计 30 分钟）"，点击打开对应页面
3. 设置模型加 `reminder_time` 字段，设置页暴露开关与时间

**涉及文件**：`backend/run_desktop.py`、`backend/app/api/settings.py`、`frontend/src/pages/SetupPage.tsx`

**完成标准**：
- [ ] 到点触发系统通知（Windows/macOS 各验一种）
- [ ] 可在设置页关闭或改时间
- [ ] 无任务的日子不打扰

## P2-1 错题回流——检验历史长出第二次生命

**问题**：测验错题存在 `VerificationRecord` 里再无消费者。学过的错处正是最该复习的地方。

**方案**：
1. 检验不通过（<70 分）时，取错题关联的知识点，调用 planner 生成 1-2 个 0.5h 的"补强任务"
2. 补强任务通过 P0-1 的增量重排插入未来日程（优先级高于普通任务，排在最近可用日）
3. 补强任务的再次检验复用现有出题逻辑，但 `_historical_question_texts` 要把原错题文本排除（避免重复出题的机制已有，确认覆盖此场景）

**涉及文件**：`backend/app/api/tasks.py`、`backend/app/llm/verifier.py`、`backend/app/services/planner_service.py`

**完成标准**：
- [ ] 检验失败自动生成补强任务并进入日程
- [ ] 补强任务再次检验不出原错题原题
- [ ] pytest 覆盖生成与排入逻辑

## P2-2 周复盘视图——预计 vs 实际照进 UI

**问题**：用户看不到"计划执行得怎么样"，弃用前的挣扎期没有任何自省工具。

**方案**：
1. 新增 `GET /api/goals/{goal_id}/review?week=YYYY-WW`：返回该周每日的预计任务数/实际完成数/实际耗时、检验通过率、重排次数
2. 前端加复盘页（或 PlanOverview 的一个 tab）：周视图 + 一行结论（"本周完成率 72%，比上周高 14%"）
3. 数据全部来自已有表（Task、VerificationRecord），无新采集成本

**涉及文件**：`backend/app/api/goals.py`、`frontend/src/pages/`（新页面）

**完成标准**：
- [ ] review 端点返回周粒度统计
- [ ] 前端展示完成率趋势
- [ ] 无数据周不报错

## P3 非均匀排程与部分进度（低优先级储备）

- **难度加权排程**：`group_tasks` 目前均匀铺排；学习曲线前松后紧，可按里程碑序号给前段减载、末段（检验密集段）留缓冲。改动集中在 `scheduler.py`，注意向后兼容现有测试。
- **部分进度**：任务模型加 `progress_percent`，勾选从二元变滑块；导师会话进行中也算部分进度。仅执行环锦上添花，优先级最低。

---

## 开发流程建议（给 Codex 的执行约定）

1. **逐任务交付**：每个任务独立分支 + 独立 commit + 对应 pytest，不合并大改动
2. **向后兼容**：所有 API 变更不破坏现有端点行为（现有测试全绿是底线）
3. **LLM 边界**：延续现有纪律——LLM 只出内容，日期/计分一律服务端算；新 LLM 输出全部过 Pydantic 校验 + 带反馈重试
4. **每完成一个任务**，在本文件对应完成标准处打勾并追加"报告"小节（commit hash + pytest 摘要 + 遗留问题），与 docs/codex/REPORT.md 的既有约定一致
5. **建议顺序**：P0-1 → P0-2 → P1-2 → P1-1 → P1-3 → P2-1 → P2-2（replan 先行，后面多个任务依赖它）
