"""APScheduler integration for periodic document scanning"""

import asyncio
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from app.database import SessionLocal
from app.models.job import JobRun
from app.services.document_service import DocumentService
from app.services.settings_service import SettingsService
from app.core.sec_client import SECAPIClient
from app.config import settings

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages the APScheduler instance and job definitions"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running_job_id: Optional[int] = None

    def start(self):
        """Start the scheduler with configured jobs"""
        # Get schedule config from database
        db = SessionLocal()
        try:
            settings_service = SettingsService(db)
            config = settings_service.get_schedule_config()
        finally:
            db.close()

        # Weekly scan job
        self.scheduler.add_job(
            self._run_scheduled_scan,
            trigger=CronTrigger(
                day_of_week=config["day_of_week"],
                hour=config["hour"],
                minute=config["minute"]
            ),
            id="weekly_scan",
            name="Weekly SEC Filing Scan",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(
            f"Scheduler started - weekly scan on day {config['day_of_week']} "
            f"at {config['hour']:02d}:{config['minute']:02d}"
        )

    def shutdown(self):
        """Gracefully shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler shut down")

    async def trigger_manual_scan(self) -> int:
        """
        Trigger an immediate scan.

        Returns:
            Job ID for tracking
        """
        return await self._run_scan("manual_scan")

    async def _run_scheduled_scan(self):
        """Wrapper for scheduled scan execution"""
        await self._run_scan("scheduled_scan")

    async def _run_scan(self, job_type: str) -> Optional[int]:
        """
        Execute a document scan.

        Returns:
            Job run ID
        """
        db = SessionLocal()
        job_run = None

        try:
            # Test API connectivity first (before creating job record)
            async with SECAPIClient(settings.SEC_API_KEY) as client:
                if not await client.test_connection():
                    logger.error("SEC API connection test failed - skipping scan")
                    # Create a failed job record
                    job_run = JobRun(
                        job_type=job_type,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        status="failed",
                        error_message="SEC API connection test failed"
                    )
                    db.add(job_run)
                    db.commit()
                    return job_run.id

                # Create job record
                job_run = JobRun(
                    job_type=job_type,
                    started_at=datetime.utcnow(),
                    status="running"
                )
                db.add(job_run)
                db.commit()
                db.refresh(job_run)

                self._running_job_id = job_run.id
                logger.info(f"Starting {job_type} scan (job_id={job_run.id})")

                # Get save path from settings
                settings_service = SettingsService(db)
                save_path = settings_service.get_document_save_path()

                # Run the scan
                document_service = DocumentService(db, client)
                result = await document_service.scan_all_funds(save_path=save_path)

                # Update job record
                job_run.status = "success" if not result.errors else "partial"
                job_run.funds_scanned = result.funds_scanned
                job_run.documents_found = result.documents_found
                job_run.documents_downloaded = result.documents_downloaded
                job_run.details = {"errors": result.errors} if result.errors else None
                job_run.completed_at = datetime.utcnow()

                logger.info(
                    f"Scan completed: {result.documents_downloaded} documents downloaded, "
                    f"{len(result.errors)} errors"
                )

        except Exception as e:
            logger.exception(f"Scan job failed: {e}")
            if job_run:
                job_run.status = "failed"
                job_run.error_message = str(e)
                job_run.completed_at = datetime.utcnow()
        finally:
            self._running_job_id = None
            db.commit()
            db.close()

        return job_run.id if job_run else None

    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time"""
        job = self.scheduler.get_job("weekly_scan")
        return job.next_run_time if job else None

    def reschedule(self, day_of_week: int, hour: int, minute: int = 0):
        """Reschedule the weekly scan"""
        self.scheduler.reschedule_job(
            "weekly_scan",
            trigger=CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute
            )
        )
        logger.info(f"Rescheduled weekly scan to day={day_of_week}, time={hour:02d}:{minute:02d}")

    def is_scan_running(self) -> bool:
        """Check if a scan is currently running"""
        return self._running_job_id is not None

    def get_running_job_id(self) -> Optional[int]:
        """Get the ID of the currently running job"""
        return self._running_job_id


# Global scheduler instance
scheduler_manager = SchedulerManager()
