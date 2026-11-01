from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.api.collections import router as collections_router
from app.api.agent import router as agent_router
from app.api.media import router as media_router
from app.api.youtube import router as youtube_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)
app.include_router(collections_router)
app.include_router(agent_router)
app.include_router(media_router)
app.include_router(youtube_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str | float]:
    started = perf_counter()
    return {
        "status": "ok",
        "service": "api",
        "environment": get_settings().environment,
        "response_time_ms": round((perf_counter() - started) * 1000, 3),
    }
