# Daybreak

**Stop dreaming, start doing.**

Daybreak is the AI companion that turns big visions into daily actions. Most people don't lack ideas — they drown in them: a goal too vague to start, a plan that never gets written, a Monday that keeps resetting. Daybreak takes any ambition, no matter how fuzzy, and turns it into a concrete day-by-day schedule in minutes. Instead of spending hours or days planning, you spend your energy doing.

It's built for people with ideas and ambition who are tired of spinning in place. Bring your goal — learn a language, launch a product, get fit, write a book — and Daybreak breaks it into milestones, places executable tasks on your calendar, verifies what you've learned, and coaches you through the hard parts. Every day, there is a next step. Every step, the vision gets a little more real.

> 中文文档：[README.zh-CN.md](README.zh-CN.md)

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg)
![Node](https://img.shields.io/badge/Node-20+-339933.svg)
![Build](https://img.shields.io/github/actions/workflow/status/3196973848/daybreak/build-desktop.yml?branch=duration-uniform-scheduling&label=build)
![Tests](https://img.shields.io/github/actions/workflow/status/3196973848/daybreak/test.yml?branch=duration-uniform-scheduling&label=tests)

## Features

- **Vision → daily action**: describe your big goal in one sentence; Daybreak turns it into milestones and a day-by-day schedule, so you never stare at a blank calendar again.
- **Minutes, not days**: a plan that would take hours of thinking is generated in seconds — stop planning, start doing.
- **Duration-based scheduling**: pick a day/week/month deadline; tasks are spread evenly across the period, including weekends. If capacity is insufficient, the app tells you the shortest feasible duration.
- **Daily execution**: calendar view, one-click task completion, effort and type labels.
- **Calendar export**: download any plan as an iCal file and import it into your calendar app.
- **Verification**: learning tasks get a fresh 10-question quiz (70/100 to pass); practice/project tasks go through a delivery review. History is stored.
- **Task-scoped AI tutor**: a coach that meets you where you are — persistent adaptive conversation (diagnose → explain → practice → remediate → ready), streaming replies, and switchable models.
- **Local-first**: your data lives on your machine in a local database; no sign-in, no cloud account.
- **English / 中文 UI**: switch language from the top bar at any time; the choice is remembered.
- **Bring your own LLM**: switch between DeepSeek, OpenAI, Claude, and local Ollama from the first-run setup wizard.
- **Packaged desktop apps**: Windows and macOS builds published automatically from GitHub Actions.

## Screenshots

![Daybreak demo](docs/screenshots/demo.gif)

The animation above is a stylized walkthrough of the core flow. Real screen captures are tracked in [docs/screenshots](docs/screenshots).

## Quick start (downloaded app)

1. Download the archive for your platform from [Releases](../../releases) (`Daybreak-v*`).
2. Run the app (Windows: `Daybreak.exe`; macOS: `Daybreak`). On first launch, a setup wizard walks you through choosing a provider (DeepSeek / OpenAI / Claude / Ollama) and entering your API key.
3. Start planning. Your browser opens automatically — no sign-up needed.

Your data is stored in `planagent.db` next to the app; back it up by copying that file. The setup wizard writes your provider choice and key to `planagent.conf`.

> macOS: if Gatekeeper blocks the unsigned app, right-click → Open, or run `xattr -dr com.apple.quarantine Daybreak`.

## Run from source

### Backend

```bash
cd backend
pip install -r requirements.txt
export DEEPSEEK_API_KEY=sk-...
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api to :8000)
```

## Configuration

All settings can be overridden with environment variables prefixed with `PLANAGENT_`:

| Variable | Description | Default |
| --- | --- | --- |
| `PLANAGENT_LLM_PROVIDER` | Provider: `deepseek` / `openai` / `anthropic` / `ollama` / `custom` | `deepseek` |
| `PLANAGENT_LLM_API_KEY` / `DEEPSEEK_API_KEY` | DeepSeek API key | empty |
| `PLANAGENT_LLM_MODEL` | Default model | `deepseek-v4-pro` |
| `PLANAGENT_LLM_MODELS` | Selectable models (comma-separated) | `deepseek-v4-pro,deepseek-chat,deepseek-reasoner` |
| `PLANAGENT_AUTH_ENABLED` | Enable account sign-in | `false` |
| `PLANAGENT_DATABASE_URL` | Database URL | local `planagent.db` |

The desktop build also reads a `planagent.conf` file next to the executable (see `planagent.conf.example`). Provider presets also accept the standard environment keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`); local Ollama needs no key.

## Architecture

The LLM decides **what** to plan; a deterministic scheduler decides **when**. This separation keeps scheduling testable and makes plans reproducible.

```mermaid
flowchart LR
    U[User] --> F[React frontend]
    F -->|REST / SSE| A[FastAPI backend]
    A --> P[Planner: LLM decomposes goal]
    A --> S[Deterministic scheduler]
    A --> T[Tutor: streaming LLM turns]
    A --> V[Verifier: quizzes & delivery review]
    P --> D[(SQLite)]
    S --> D
    T --> D
    V --> D
    P -->|DeepSeek / OpenAI-compatible| L[LLM API]
    T --> L
    V --> L
```

### Project layout

```text
daybreak/
├── backend/            FastAPI app (LLM, scheduler, services, API, tests)
├── frontend/           React + Vite app
├── docs/               Design and implementation docs
├── .github/            CI/CD workflows and PR template
├── planagent.conf.example
├── planagent.spec      PyInstaller packaging config
└── Dockerfile / docker-compose.yml
```

## Testing

```bash
cd backend && python -m pytest
cd frontend && npm test && npm run build
```

## Release process

Push a `v*` tag (e.g. `v1.0.0`) and GitHub Actions builds Windows and macOS packages and attaches them to a GitHub Release. You can also run the **Build desktop packages** workflow manually and grab the artifacts.

### Code signing (optional)

Official releases are shipped unsigned, so Windows may show *Unknown publisher* and macOS may show *unidentified developer* on first launch (see the note above). The workflow will sign automatically once you configure the corresponding repository secrets:

| Platform | Secrets | Method |
| --- | --- | --- |
| macOS | `AC_CERTIFICATE_BASE64`, `AC_P12_PASSWORD`, `APPLE_CERT_NAME` | Apple Developer certificate (`codesign`) |
| Windows | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_ENDPOINT`, `AZURE_SIGNING_ACCOUNT`, `AZURE_CERT_PROFILE` | Azure Trusted Signing (`azure/artifact-signing-action`) |
| Windows (self-signed) | `WINDOWS_PFX_BASE64`, `WINDOWS_PFX_PASSWORD` | `.pfx` certificate + `signtool` (only reduces the *Unknown publisher* warning; it does not remove SmartScreen) |

Any step whose secrets are not set is skipped automatically, so a fork with no signing credentials still produces working builds. See [SECURITY.md](SECURITY.md) for the full hardening notes.

## Roadmap

- [ ] Screenshots and an online demo
- [ ] First-run setup wizard for API keys
- [ ] OpenAI, Claude, and local (Ollama) providers
- [ ] English UI
- [x] Calendar export (iCal)
- [ ] Calendar import
- [ ] Reminders
- [ ] Adaptive replanning when you fall behind
- [ ] Plan templates / community presets

## FAQ

- **Legacy database error `no column named user_id`?** The app auto-migrates older databases on startup — nothing to do.
- **Port 8000 already in use?** Stop the process using it, or switch ports and update the frontend proxy.
- **AI not responding?** Verify your DeepSeek API key in `planagent.conf` or the environment, and that your account has quota.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
