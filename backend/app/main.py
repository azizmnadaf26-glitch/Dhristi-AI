import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validate_settings
from app.db import engine as db_engine
from app.errors import _error_response, register_error_handlers
from app.startup_checks import run_startup_checks
from app.routers import admin, auth, cases, evaluation, images, meta, simulations
from app.services import engine_adapter, job_queue, job_sweeper

validate_settings()

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: bring the engine up (fake in development) and start the worker thread.
    run_startup_checks(db_engine)  # refuses to start if migrations are behind
    engine_adapter.set_failed(False)
    try:
        engine_adapter.get_adapter()
    except Exception:
        engine_adapter.set_failed(True)
        logger.exception("Engine failed to start; health will report it as down")
    job_queue.queue.start()
    job_sweeper.sweeper.start()
    yield
    # Shutdown: stop accepting jobs, let the active job finish (up to 30 s), stop the engine.
    job_sweeper.sweeper.stop()
    job_queue.queue.shutdown(30)
    engine_adapter.reset_adapter()


app = FastAPI(
    title="RetinaGuide XAI API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

register_error_handlers(app)
app.include_router(auth.router)
app.include_router(auth.me_router)
app.include_router(cases.router)
app.include_router(images.router)
app.include_router(meta.router)
app.include_router(admin.router)
app.include_router(evaluation.router)
app.include_router(simulations.router)

_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


def _body_too_large(request: Request):
    """Runs before authentication. Returns an error response, or None if the size is fine."""
    declared = request.headers.get("content-length")
    if declared is None:
        return None
    try:
        size = int(declared)
    except ValueError:
        return _error_response(request, 400, "bad_request", "Invalid Content-Length header")
    limit = (settings.max_upload_mb + 1) * 1024 * 1024  # file limit plus 1 MB overhead
    if size > limit:
        return _error_response(
            request, 413, "file_too_large", f"Request is larger than {settings.max_upload_mb} MB"
        )
    return None


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()

    response = _body_too_large(request)
    if response is None:
        response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = str(duration_ms)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    path = request.url.path
    if not path.startswith("/api/docs"):  # the docs page loads scripts from a CDN
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    if path.startswith("/api"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/api/health")
def health():
    state = engine_adapter.engine_state()
    db_ok = False
    try:
        from sqlalchemy import text
        from app.db import SessionLocal

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    adapter = getattr(engine_adapter, "_adapter", None)
    model_loaded = False
    if adapter is not None and getattr(adapter, "_net", None) is not None:
        model_loaded = True
    elif settings.matlab_fake and state == "up":
        model_loaded = True

    overall_ok = (state != "down") and db_ok
    return {
        "status": "ok" if overall_ok else "degraded",
        "backend": "up",
        "database": "up" if db_ok else "down",
        "engine": "fake" if settings.matlab_fake else "real",
        "engine_state": state,
        "matlab_engine": state if not settings.matlab_fake else "disabled",
        "model_loaded": model_loaded,
    }