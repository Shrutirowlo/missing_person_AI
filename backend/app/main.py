"""Application entrypoint: FastAPI + MongoDB + versioned routers + Swagger."""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .api import admin, auth, dataset, history, images, ngo, persons, recognition, users  # noqa: E402
from .config import settings  # noqa: E402
from .db import ensure_indexes, get_db, ping_db  # noqa: E402
from .utils.images import ensure_dir  # noqa: E402

logger = logging.getLogger("missing_person_ai.warmup")


async def _warm_ai_models() -> None:
    """Pre-load the ORIGINAL AI models once, in the background, at startup.

    First-request cold start (TensorFlow + InsightFace artifact loading) is
    the dominant cause of recognition timeouts: the adapters are singletons
    and load lazily, so the first /recognition/search paid 60-120s+ while
    holding inference locks under CPU contention. Warming here moves that
    one-time cost off the request path; per-request inference stays
    unchanged (fast, cached, per-model isolated). Original artifacts are
    only read, never modified. A model that is genuinely unavailable
    (e.g. missing MediaPipe task file) logs its real error and stays
    unavailable — nothing is substituted."""
    from .ai import registry

    for name, get in (("cnn", registry.get_cnn),
                      ("arcface", registry.get_arcface),
                      ("mediapipe_knn", registry.get_mediapipe_knn)):
        started = time.perf_counter()
        try:
            ok = await asyncio.to_thread(get().load)
            logger.info("AI warmup: %s loaded=%s in %.1fs",
                        name, ok, time.perf_counter() - started)
        except Exception as exc:
            logger.warning("AI warmup: %s failed after %.1fs: %s",
                           name, time.perf_counter() - started, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dir(settings.storage_dir)
    try:
        await ping_db()
        await ensure_indexes()
        app.state.db_ready = True
    except Exception as exc:
        app.state.db_ready = False
        app.state.db_error = str(exc)
    # Fire-and-forget: serve traffic immediately while models warm up.
    asyncio.get_running_loop().create_task(_warm_ai_models())
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.api_prefix
app.include_router(auth.router, prefix=prefix)
app.include_router(users.router, prefix=prefix)
app.include_router(persons.router, prefix=prefix)
app.include_router(images.router, prefix=prefix)
app.include_router(recognition.router, prefix=prefix)
app.include_router(history.router, prefix=prefix)
app.include_router(dataset.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
app.include_router(ngo.router, prefix=prefix)

app.mount("/storage", StaticFiles(directory=ensure_dir(settings.storage_dir)), name="storage")


@app.get("/healthz", tags=["health"])
async def healthz():
    try:
        await ping_db()
        db = "up"
    except Exception as exc:
        db = f"down: {exc}"
    return {"status": "ok", "db": db}


@app.get("/", tags=["health"])
async def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/healthz"}
