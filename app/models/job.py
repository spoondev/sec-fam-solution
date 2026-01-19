from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from datetime import datetime
from app.database import Base


class JobRun(Base):
    """Tracks scheduler job execution history"""
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50), nullable=False)  # "scheduled_scan" or "manual_scan"
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime)
    status = Column(String(20), nullable=False)  # "running", "success", "failed", "partial"
    funds_scanned = Column(Integer, default=0)
    documents_found = Column(Integer, default=0)
    documents_downloaded = Column(Integer, default=0)
    error_message = Column(Text)
    details = Column(JSON)

    def __repr__(self):
        return f"<JobRun(id={self.id}, type={self.job_type}, status={self.status})>"
