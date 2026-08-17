# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-08-17

首个正式发布版本。

### 新增

- 目标驱动的计划流程：输入目标 → AI 拆解里程碑与每日任务 → 确定性排程。
- 时长与每日投入排程：按天/周/月换算截止日，任务均匀铺满周期，容量不足时给出建议。
- 计划总览、每日任务、月历、进度追踪与任务完成勾选。
- 任务检验：学习任务 10 题测验、实操/项目交付评审，70 分通过制。
- 任务级 AI 导师：持久化对话、阶段流水线、流式回复、可切换模型。
- 本地单用户模式（默认无登录）；保留多账号后端能力。
- 旧数据库自动迁移（`goals.user_id` 等）。
- Windows / macOS 桌面打包，GitHub Actions 自动构建并发布到 Releases。

### 说明

- 桌面版需要用户自行配置 DeepSeek API Key（`planagent.conf` 或环境变量）。
- macOS 未签名，首次打开需右键 → 打开，或执行 `xattr -dr com.apple.quarantine PlanAgent`。
