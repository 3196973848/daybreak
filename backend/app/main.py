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
