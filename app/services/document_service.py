"""Document retrieval and management service"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.models.fund import Fund
from app.models.document import Document
from app.core.sec_client import SECAPIClient, SECFiling
from app.core.document_processor import DocumentProcessor
from app.core.exceptions import (
    APIConnectionError,
    APIRateLimitError,
    DocumentDownloadError,
    StorageError,
)
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a document scan operation"""
    funds_scanned: int = 0
    documents_found: int = 0
    documents_downloaded: int = 0
    errors: list[dict] = field(default_factory=list)


class DocumentService:
    """Handles document scanning and retrieval"""

    FORM_TYPES = ["N-CSR", "N-CSRS"]
    DEFAULT_LOOKBACK_DAYS = 730  # 2 years for initial scan

    def __init__(self, db: Session, api_client: Optional[SECAPIClient] = None):
        self.db = db
        self.api_client = api_client

    def get_documents(
        self,
        fund_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 25
    ) -> tuple[list[Document], int]:
        """Get documents with optional filtering and pagination"""
        query = self.db.query(Document)

        if fund_id:
            query = query.filter(Document.fund_id == fund_id)

        total = query.count()

        documents = (
            query
            .order_by(Document.filed_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return documents, total

    def get_document_by_accession(self, accession_number: str) -> Optional[Document]:
        """Get document by accession number"""
        return (
            self.db.query(Document)
            .filter(Document.accession_number == accession_number)
            .first()
        )

    def get_document_count(self) -> int:
        """Get total document count"""
        return self.db.query(Document).count()

    def get_recent_documents(self, limit: int = 10) -> list[Document]:
        """Get most recently filed documents"""
        return (
            self.db.query(Document)
            .order_by(Document.filed_at.desc())
            .limit(limit)
            .all()
        )

    async def scan_all_funds(self, save_path: Optional[str] = None) -> ScanResult:
        """Scan all active funds for new documents"""
        result = ScanResult()

        # Get all active funds
        funds = self.db.query(Fund).filter(Fund.is_active == True).all()
        logger.info(f"Starting scan for {len(funds)} active funds")

        # Determine save path
        save_path = save_path or settings.DOCUMENT_SAVE_PATH
        processor = DocumentProcessor(save_path)

        for fund in funds:
            try:
                fund_result = await self._scan_fund(fund, processor)
                result.funds_scanned += 1
                result.documents_found += fund_result.documents_found
                result.documents_downloaded += fund_result.documents_downloaded
                result.errors.extend(fund_result.errors)

                # Small delay between funds to avoid rate limiting
                await asyncio.sleep(0.5)

            except APIConnectionError as e:
                logger.error(f"API connection failed for fund {fund.cik}: {e}")
                result.errors.append({
                    "fund_cik": fund.cik,
                    "error_type": "connection",
                    "message": str(e)
                })
            except APIRateLimitError as e:
                logger.warning(f"Rate limit hit, pausing: {e}")
                await asyncio.sleep(e.retry_after or 60)
                # Retry the fund
                try:
                    fund_result = await self._scan_fund(fund, processor)
                    result.funds_scanned += 1
                    result.documents_found += fund_result.documents_found
                    result.documents_downloaded += fund_result.documents_downloaded
                except Exception as retry_error:
                    result.errors.append({
                        "fund_cik": fund.cik,
                        "error_type": "retry_failed",
                        "message": str(retry_error)
                    })
            except Exception as e:
                logger.exception(f"Unexpected error scanning fund {fund.cik}")
                result.errors.append({
                    "fund_cik": fund.cik,
                    "error_type": "unknown",
                    "message": str(e)
                })

        logger.info(
            f"Scan complete: {result.funds_scanned} funds, "
            f"{result.documents_found} found, {result.documents_downloaded} downloaded"
        )
        return result

    async def _scan_fund(self, fund: Fund, processor: DocumentProcessor) -> ScanResult:
        """Scan a single fund for new documents"""
        result = ScanResult()

        # Determine date range - from last retrieval or default lookback
        last_doc = (
            self.db.query(Document)
            .filter(Document.fund_id == fund.id)
            .order_by(Document.filed_at.desc())
            .first()
        )

        if last_doc:
            from_date = last_doc.filed_at.date()
        else:
            # Default: look back 2 years for initial scan
            from_date = date.today() - timedelta(days=self.DEFAULT_LOOKBACK_DAYS)

        logger.info(f"Scanning fund {fund.cik} ({fund.name}) from {from_date}")

        # Search for filings
        filings = await self.api_client.search_filings(
            ciks=[fund.cik],
            form_types=self.FORM_TYPES,
            from_date=from_date
        )

        result.documents_found = len(filings)
        logger.info(f"Found {len(filings)} filings for fund {fund.cik}")

        for filing in filings:
            # Check if already downloaded
            existing = self.get_document_by_accession(filing.accession_number)
            if existing:
                logger.debug(f"Skipping already downloaded: {filing.accession_number}")
                continue

            try:
                await self._download_and_save(fund, filing, processor)
                result.documents_downloaded += 1
            except DocumentDownloadError as e:
                logger.error(f"Failed to download {filing.accession_number}: {e}")
                result.errors.append({
                    "fund_cik": fund.cik,
                    "accession_number": filing.accession_number,
                    "error_type": "download",
                    "message": str(e)
                })
            except StorageError as e:
                logger.error(f"Failed to save {filing.accession_number}: {e}")
                result.errors.append({
                    "fund_cik": fund.cik,
                    "accession_number": filing.accession_number,
                    "error_type": "storage",
                    "message": str(e)
                })
            except Exception as e:
                logger.error(f"Error processing {filing.accession_number}: {e}")
                result.errors.append({
                    "fund_cik": fund.cik,
                    "accession_number": filing.accession_number,
                    "error_type": "unknown",
                    "message": str(e)
                })

        return result

    async def _download_and_save(
        self,
        fund: Fund,
        filing: SECFiling,
        processor: DocumentProcessor
    ) -> Document:
        """Download and save a single filing document"""
        # Find primary document
        primary_doc = processor.find_primary_document(filing)
        if not primary_doc:
            raise DocumentDownloadError(
                filing.accession_number,
                "No downloadable document found"
            )

        # Build download URL
        doc_filename = primary_doc.get("documentUrl", "").split("/")[-1]
        download_url = self.api_client.build_download_url(
            cik=filing.cik,
            accession_number=filing.accession_number,
            filename=doc_filename
        )

        logger.info(f"Downloading: {download_url}")

        # Download document
        try:
            content = await self.api_client.download_document(download_url)
        except Exception as e:
            raise DocumentDownloadError(download_url, str(e))

        # Generate filename
        extension = processor.get_file_extension(primary_doc)
        filename = processor.generate_filename(
            fund_name=fund.name or filing.company_name or f"CIK-{fund.cik}",
            ticker=fund.ticker or filing.ticker,
            reporting_date=filing.period_of_report,
            form_type=filing.form_type,
            extension=extension
        )

        # Save to disk
        try:
            local_path, file_size = processor.save_document(
                content=content,
                filename=filename,
                subfolder=fund.ticker or fund.cik
            )
        except Exception as e:
            raise StorageError(f"Failed to save {filename}: {e}")

        # Update fund info if we got new data
        if not fund.name and filing.company_name:
            fund.name = filing.company_name
        if not fund.ticker and filing.ticker:
            fund.ticker = filing.ticker

        # Create document record
        document = Document(
            fund_id=fund.id,
            accession_number=filing.accession_number,
            form_type=filing.form_type,
            filed_at=filing.filed_at,
            reporting_period_end=filing.period_of_report,
            document_url=download_url,
            local_filename=filename,
            local_path=local_path,
            file_size_bytes=file_size
        )

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        logger.info(f"Saved document: {filename}")
        return document
