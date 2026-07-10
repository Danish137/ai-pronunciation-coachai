from contextlib import asynccontextmanager
import logging
import shutil

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.assessments import router as assessments_router
from .core.config import get_settings
from .core.database import create_tables, resolved_database_path, resolved_database_url
from .services.retention import purge_expired_attempts

settings = get_settings()
logger = logging.getLogger("pronounceai")
_scheduler: BackgroundScheduler | None = None


def _verify_media_binaries() -> None:
    missing = [
        binary for binary in (settings.ffmpeg_binary, settings.ffprobe_binary)
        if shutil.which(binary) is None
    ]
    if missing:
        raise RuntimeError(
            f"Missing required media binary on PATH: {', '.join(missing)}"
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _scheduler

    _verify_media_binaries()
    create_tables()
    scheduler_started = False
    deleted = purge_expired_attempts(settings.attempt_retention_days)
    logger.info(
        "Attempt retention startup purge completed | retention_days=%d | deleted=%d",
        settings.attempt_retention_days,
        deleted,
    )
    if _scheduler is None or not _scheduler.running:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            purge_expired_attempts,
            trigger="cron",
            hour=settings.retention_purge_hour_utc,
            kwargs={"retention_days": settings.attempt_retention_days},
            id="attempt-retention-purge",
            replace_existing=True,
        )
        _scheduler.start()
        scheduler_started = True

    logger.info(
        "Startup | environment=%s | database=%s | database_url=%s | scheduler=%s | azure_configured=%s | groq_configured=%s",
        settings.app_env,
        resolved_database_path(),
        resolved_database_url(),
        "started" if scheduler_started else "already-running",
        bool(settings.azure_speech_key and settings.azure_speech_region),
        bool(settings.groq_api_key),
    )

    try:
        yield
    finally:
        if _scheduler is not None and _scheduler.running:
            _scheduler.shutdown(wait=True)
            logger.info("Shutdown | scheduler=stopped")


app = FastAPI(
    title="PronounceAI API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessments_router, prefix="/api")


@app.get("/health")
def healthcheck() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "mock_mode_enabled": settings.enable_mock_analysis,
        "azure_key_configured": bool(settings.azure_speech_key),
        "azure_region_configured": bool(settings.azure_speech_region),
        "groq_key_configured": bool(settings.groq_api_key),
    }
