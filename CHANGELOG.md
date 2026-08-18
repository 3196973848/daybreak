# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- 英文界面：顶部导航一键切换中英文，选择会被记住；所有页面文案均已翻译。
- 可选代码签名：配置签名 secrets 后，构建工作流会自动对 Windows / macOS 安装包签名；未配置时自动跳过，不影响发布。

### 品牌

- 项目更名为 **Daybreak**，定位为「把大愿景变成每日行动」：停止空想，开始行动。

## [1.0.2] - 2026-08-17

首个对外发布版本（`v1.0.0` / `v1.0.1` 为内部占位标签、未产出安装包，已清理）。

### 新增

- 多模型提供方：DeepSeek / OpenAI / Claude / 本地 Ollama / 自定义 OpenAI 兼容端点。
- 首次运行引导页：选择提供方、填写 API Key、选择默认模型，并写入 `planagent.conf`。
- AI 导师流式回复、模型切换、Enter 发送（Shift+Enter 换行）。
- iCal 日历导出。
- 测试 CI、演示动画、中英文 README 完善。

### 修复

- 发布工作流 YAML 无效导致 GitHub Actions 无法生成 Release。
- 旧数据库缺少 `goals.user_id` 时自动迁移。

## [1.0.0] - 2026-08-17

初始版本（内部占位，未对外发布）。

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
- macOS 未签名，首次打开需右键 → 打开，或执行 `xattr -dr com.apple.quarantine Daybreak`。
