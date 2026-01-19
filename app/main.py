"""FastAPI application entry point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

from app.api.routes import router
from app.database import engine, Base
from app.core.scheduler import scheduler_manager
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown"""
    # Startup
    logger.info("Starting SEC Filing Manager...")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")

    # Ensure data directories exist
    Path(settings.DOCUMENT_SAVE_PATH).mkdir(parents=True, exist_ok=True)

    # Start scheduler
    scheduler_manager.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler_manager.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="SEC Filing Manager",
    description="Automated retrieval and management of SEC N-CSR/N-CSRS filings",
    version="1.0.0",
    lifespan=lifespan
)

# Include routes
app.include_router(router)
