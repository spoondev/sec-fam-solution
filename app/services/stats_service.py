"""Statistics and reporting service"""

from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.fund import Fund
from app.models.document import Document
from app.models.job import JobRun


@dataclass
class FundStats:
    """Statistics for a single fund"""
    id: int
    cik: str
    name: Optional[str]
    ticker: Optional[str]
    document_count: int
    latest_filing: Optional[datetime]
    avg_frequency_days: Optional[int]


class StatsService:
    """Handles statistics calculations and reporting"""

    def __init__(self, db: Session):
        self.db = db

    def get_fund_count(self, active_only: bool = True) -> int:
        """Get count of funds"""
        query = self.db.query(Fund)
        if active_only:
            query = query.filter(Fund.is_active == True)
        return query.count()

    def get_document_count(self) -> int:
        """Get total document count"""
        return self.db.query(Document).count()

    def get_recent_documents(self, limit: int = 10) -> list[Document]:
        """Get most recently filed documents with fund info loaded"""
        return (
            self.db.query(Document)
            .join(Fund)
            .order_by(Document.filed_at.desc())
            .limit(limit)
            .all()
        )

    def get_last_job_run(self) -> Optional[JobRun]:
        """Get the most recent job run"""
        return (
            self.db.query(JobRun)
            .order_by(JobRun.started_at.desc())
            .first()
        )

    def get_job_by_id(self, job_id: int) -> Optional[JobRun]:
        """Get job run by ID"""
        return self.db.query(JobRun).filter(JobRun.id == job_id).first()

    def get_fund_statistics(self) -> list[FundStats]:
        """Get statistics for all active funds"""
        funds = (
            self.db.query(Fund)
            .filter(Fund.is_active == True)
            .order_by(Fund.name, Fund.cik)
            .all()
        )

        stats = []
        for fund in funds:
            # Get document count and latest filing
            doc_query = (
                self.db.query(
                    func.count(Document.id).label("count"),
                    func.max(Document.filed_at).label("latest")
                )
                .filter(Document.fund_id == fund.id)
                .first()
            )

            doc_count = doc_query.count if doc_query else 0
            latest_filing = doc_query.latest if doc_query else None

            # Calculate average frequency
            avg_freq = None
            if doc_count > 1:
                # Get all filing dates
                filing_dates = (
                    self.db.query(Document.filed_at)
                    .filter(Document.fund_id == fund.id)
                    .order_by(Document.filed_at)
                    .all()
                )
                if len(filing_dates) > 1:
                    dates = [d[0] for d in filing_dates]
                    total_days = (dates[-1] - dates[0]).days
                    avg_freq = total_days // (len(dates) - 1)

            stats.append(FundStats(
                id=fund.id,
                cik=fund.cik,
                name=fund.name,
                ticker=fund.ticker,
                document_count=doc_count,
                latest_filing=latest_filing,
                avg_frequency_days=avg_freq
            ))

        return stats

    def get_job_history(self, limit: int = 20) -> list[JobRun]:
        """Get recent job run history"""
        return (
            self.db.query(JobRun)
            .order_by(JobRun.started_at.desc())
            .limit(limit)
            .all()
        )

    def get_documents_by_month(self, months: int = 12) -> dict[str, int]:
        """Get document counts grouped by month"""
        start_date = datetime.utcnow() - timedelta(days=months * 30)

        results = (
            self.db.query(
                func.strftime("%Y-%m", Document.filed_at).label("month"),
                func.count(Document.id).label("count")
            )
            .filter(Document.filed_at >= start_date)
            .group_by(func.strftime("%Y-%m", Document.filed_at))
            .order_by(func.strftime("%Y-%m", Document.filed_at))
            .all()
        )

        return {row.month: row.count for row in results}
