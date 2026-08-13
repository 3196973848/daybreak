# Task 1: 后端脚手架 + 健康检查

## 目标

搭建 FastAPI 后端骨架:config、database、main 应用,`GET /api/health` 返回 `{"status": "ok"}`,并写好测试基建(pytest + TestClient)。

## 权威来源

实施计划 `docs/superpowers/plans/2026-08-13-planagent-implementation.md` 的 **Task 1** 一节。

## 要创建的文件

- `backend/requirements.txt`
- `backend/app/__init__.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/main.py`
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/test_health.py`
- `backend/pytest.ini`

## 实现内容

### `backend/requirements.txt`
```
fastapi>=0.115
uvicorn[standard]>=0.34
sqlalchemy>=2.0
pydantic>=2.7
pydantic-settings>=2.3
anthropic>=0.116
httpx>=0.27
pytest>=8
```

### `backend/app/config.py`
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./planagent.db"
    blocks_per_day: int = 2
    hours_per_block: float = 1.0
    anthropic_model: str = "claude-opus-4-8"

    model_config = {"env_prefix": "PLANAGENT_"}


settings = Settings()
```

### `backend/app/database.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  ensure models are registered on Base

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### `backend/app/main.py`
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PlanAgent", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

### `backend/tests/conftest.py`
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### `backend/tests/test_health.py`
```python
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
```

### `backend/pytest.ini`
```
[pytest]
pythonpath = .
```

注:`app/__init__.py` 与 `tests/__init__.py` 为空的包标记文件。

## 完成标准

1. `cd backend && python -m pytest tests/test_health.py -v` → `1 passed`
2. 创建 git commit(`feat: backend scaffold with health check`)
3. 在任务卡末尾"报告"区写:提交 hash、测试摘要、concerns

## 提交命令

```bash
git add backend/requirements.txt backend/app backend/tests backend/pytest.ini
git commit -m "feat: backend scaffold with health check"
```

## 报告

- 提交 hash: `195187b`
- pytest 摘要: `python -m pytest tests/test_health.py -v` → `1 passed, 1 warning in 0.04s`
- concerns:
  - 当前受限沙箱禁止在 `backend/` 创建 SQLite 文件，因此验收命令在获批的沙箱外执行。
  - FastAPI 0.141.1 / Starlette 1.6.0 对当前 `TestClient` 兼容层产生 1 条 `StarletteDeprecationWarning`，不影响测试通过。
  - 为使本任务的 `init_db()` 在 Task 02 前可独立启动，创建了最小 `app/models.py` 占位；Task 02 将用正式模型内容替换。
