# PlanAgent

目标驱动的规划 Web 应用：输入一个目标，AI 拆解成里程碑和每日任务，排程算法排出日程，支持勾选完成与「去检验」验证。

## 排程规则

创建目标时输入正整数预期时长，并选择天、周或月。服务端以创建当天为开始日，计算并保存目标截止日期，再按任务顺序把计划均匀铺到整个自然日区间；周末也会安排任务。首个任务安排在当天，最后一个任务不晚于截止日。

创建目标时还可填写每日可投入时间，默认 2 小时。AI 会自行识别目标涉及的领域，把宽泛内容拆成以 0.5 小时为粒度的具体子任务；每天的任务数量可以不同，但累计预计耗时不会超过每日预算。任务组仍会包含周末地均匀铺满整个预期周期。若周期容量不足，系统不会创建计划，而会显示所需小时数和建议的最短天数。

学习任务的每次检验会重新生成 10 道题（7 道选择题、3 道简答题）。每题 10 分：选择题由服务端按正确答案计分，简答题由 AI 按评分点逐题计分；总分达到 70 分即通过。

`POST /api/goals` 使用 `duration_value` 与 `duration_unit`（`day` / `week` / `month`）。旧客户端仍可提交 `target_date`；未提供任何期限时保留按每日容量尽快安排的行为。

## AI 导师（学习任务）

学习类任务会显示「开始学习 / 继续学习」入口，进入任务级 AI 导师对话页。导师按「诊断 → 讲解 → 练习 → 补强 → ready」自适应推进，并持久化完整对话历史；刷新后可从上次进度继续，同一客户端消息不会重复调用模型。

导师复用 DeepSeek 配置（`DEEPSEEK_API_KEY`，经 `PLANAGENT_LLM_API_KEY` 读取），只接收滚动摘要和最近 12 轮对话。`ready_for_verification` 仅为建议，不直接完成任务；任务仍由原有检验流程判定（学习任务为 10 题、总分 70 分通过），通过后才会标记完成。

当前版本不包含联网检索、文件上传、语音、多用户或全局导师。

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

## 部署（对外分享）

构建并运行 Docker 镜像（需要一台服务器 / 域名）：

```bash
# 1. 准备环境变量
export PLANAGENT_AUTH_SECRET=$(openssl rand -hex 32)   # 会话签名密钥，必须设置
export PLANAGENT_LLM_API_KEY=sk-...                    # DeepSeek key

# 2. 构建并启动
docker compose up -d --build
```

- 应用监听 `8000`；前端静态文件由后端一并托管，`/` 与子路由都指向 SPA。
- 数据保存在 Docker 卷 `planagent-data`（SQLite），升级容器不丢数据。
- 对外公开请在前面加 HTTPS 反向代理（Caddy / Nginx），`PLANAGENT_AUTH_COOKIE_SECURE=true` 已在 compose 中设置。
- 默认是本地单用户模式（`PLANAGENT_AUTH_ENABLED=false`），无需登录；若需多账号，设置 `PLANAGENT_AUTH_ENABLED=true` 并恢复登录页路由。

## 本地分发（Windows exe）

把 `dist/PlanAgent.exe` 与 `planagent.conf` 放在同一目录分发给用户：

1. 将 `planagent.conf.example` 改名为 `planagent.conf` 并填入用户自己的 `PLANAGENT_LLM_API_KEY`。
2. 保持 `PLANAGENT_AUTH_ENABLED=false`，本地单用户模式无需登录。
3. 双击 `PlanAgent.exe`，浏览器会自动打开 `http://127.0.0.1:8000`。

数据保存在 exe 同目录的 `planagent.db` 中，备份该文件即可迁移。

重新打包 exe：

```bash
python -m venv .venv_build
.venv_build/Scripts/pip install -r backend/requirements.txt pyinstaller
cd frontend && npm run build
cd ..
Copy-Item frontend/dist/* backend/static -Recurse -Force
.venv_build/Scripts/pyinstaller planagent.spec --noconfirm --clean
```

## 自动构建（GitHub Actions）

把仓库推送到 GitHub 后，在 Actions 页面手动触发 **Build desktop packages**，或推送 `v*` 标签自动构建；会同时产出 Windows 与 macOS 两个安装包（在 Actions 的 Artifacts 中下载）。

- macOS 包是未签名可执行文件，首次打开若被系统拦截：右键 → 打开，或执行 `xattr -dr com.apple.quarantine PlanAgent`。
- 如需 Linux 包，把 workflow 的 `os` 矩阵加上 `ubuntu-latest` 即可。

## 结构
- `backend/app/llm` — LLM 编排(计划生成、检验出题/判分)
- `backend/app/scheduler` — 确定性排程算法
- `backend/app/services` — 计划生成服务(LLM+排程+落库)
- `backend/app/api` — REST 路由
- `frontend/src` — React 前端
