# Codex 交接包 — PlanAgent 后端实现

> 你是 **Codex**,负责实现 PlanAgent 的**后端**(Task 1-8)。Claude Code(我)负责**前端**(Task 9-13)。我们并行开发,文件树不重叠:`backend/`(你)vs `frontend/`(我)。

## 你要做什么

按顺序实现 8 个后端任务,每个任务一个文件 `docs/codex/tasks/task-NN-*.md`,内含**完整的文件内容、测试、提交命令**。严格照任务卡实现,不要自行发挥、不要做任务卡未要求的事。

## 权威来源

- **每个任务的完整代码与测试** → 对应任务卡文件(唯一要求来源,精确值照抄)
- **设计依据** → `docs/superpowers/specs/2026-08-13-planagent-design.md`
- **全量实施计划** → `docs/superpowers/plans/2026-08-13-planagent-implementation.md`(任务卡是它的后端 Task 1-8 的提炼)

若任务卡与 spec 冲突,以 spec 为准;拿不准就按任务卡文本。

## 全局约束(每个任务都遵守)

- 数据模型按 spec §4:Goal → 1 Plan → N Milestone → N Task,另加 VerificationRecord
- LLM 调用统一走 Anthropic Python SDK 的 `client.messages.parse(..., output_format=Model)`,模型 ID 用 `claude-opus-4-8`,`thinking={"type": "adaptive"}`
- LLM 只输出"是什么",绝不输出具体日期;日期一律由 `schedule()` 算法产生
- 检验通过阈值:测试/交付的 `score >= 0.7` 判通过(服务端计算,不依赖 LLM 返回 passed)
- API key 走环境变量或 Anthropic SDK 的 OAuth profile(本项目已配置),不硬编码
- 所有后端路由前缀为 `/api`
- 测试用 pytest;在 `backend/` 目录下运行 `python -m pytest`

## 工作顺序(逐个任务,不要并行)

1. 读 `docs/codex/tasks/task-01-*.md` → 创建其列出的文件 → 装依赖 → 跑 `pytest` 通过 → 按卡内提交命令 commit → 在任务卡末尾"报告"区记录:提交 hash、pytest 摘要、concerns
2. 然后 task-02 → task-03 → … → task-08,依次进行
3. 每个任务独立 commit,commit message 用任务卡给定的,不要 amend

## 环境健康检查(开始前先做)

如果你在实现中遇到 SSL 证书 / 网络 / 依赖问题,先检查:

- `SSL_CERT_FILE` 环境变量若指向不存在的 `D:\conda\envs\dl2025/ssl/cacert.pem`,请 **unset 它**(或改用系统证书),否则 SDK 与 pip 的 HTTPS 会失败
- 确认 `python --version` ≥ 3.10 可用,`pip` 正常
- 后端依赖装进当前 Python 环境即可(用 `pip install -r backend/requirements.txt`)

## 完成后

8 个任务全部提交后,在 `docs/codex/REPORT.md` 写一份总结:每个任务的提交 hash、全部 `pytest` 结果、遗留问题。Claude Code 会做集成与最终 review。
