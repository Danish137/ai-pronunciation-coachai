from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.assessments import router as assessments_router
from .core.config import get_settings
from .core.database import create_tables

settings = get_settings()
logger = logging.getLogger("pronounceai")


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    logger.warning(
        "PronounceAI startup config | mock=%s | azure_key=%s | azure_region=%s | groq_key=%s",
        settings.enable_mock_analysis,
        bool(settings.azure_speech_key),
        bool(settings.azure_speech_region),
        bool(settings.groq_api_key),
    )
    yield


app = FastAPI(
    title="PronounceAI API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
