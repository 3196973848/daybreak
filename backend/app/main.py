from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, goals, learning, tasks
from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PlanAgent", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(goals.router)
app.include_router(learning.router)
app.include_router(tasks.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


_DIST = Path(__file__).resolve().parent.parent / "static"
if _DIST.exists():
    app.mount(
        "/assets", StaticFiles(directory=_DIST / "assets"), name="assets"
    )

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = _DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
