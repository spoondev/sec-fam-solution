"""SEC API client for interacting with sec-api.io"""

import httpx
from typing import Optional
from datetime import datetime, date
from dataclasses import dataclass
import logging

from app.core.exceptions import (
    APIConnectionError,
    APIAuthenticationError,
    APIRateLimitError,
)

logger = logging.getLogger(__name__)


@dataclass
class SECFiling:
    """Represents a filing returned from SEC API"""
    accession_number: str
    form_type: str
    filed_at: datetime
    company_name: str
    cik: str
    ticker: Optional[str]
    document_files: list[dict]
    period_of_report: Optional[date]


class SECAPIClient:
    """Client for interacting with sec-api.io"""

    QUERY_API_URL = "https://api.sec-api.io"
    DOWNLOAD_API_URL = "https://archive.sec-api.io"
    MAX_PAGE_SIZE = 50

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            headers={"Authorization": self.api_key},
            timeout=60.0
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def test_connection(self) -> bool:
        """Test API connectivity with a minimal query"""
        try:
            response = await self._client.post(
                self.QUERY_API_URL,
                json={
                    "query": 'formType:"10-K"',
                    "from": "0",
                    "size": "1"
                }
            )
            if response.status_code == 401:
                raise APIAuthenticationError("Invalid API key")
            return response.status_code == 200
        except httpx.RequestError as e:
            logger.error(f"API connection test failed: {e}")
            return False

    async def search_filings(
        self,
        ciks: list[str],
        form_types: list[str],
        from_date: date,
        to_date: Optional[date] = None
    ) -> list[SECFiling]:
        """
        Search for filings matching criteria.

        Args:
            ciks: List of CIK numbers (without leading zeros)
            form_types: List of form types (e.g., ["N-CSR", "N-CSRS"])
            from_date: Start date for filed_at range
            to_date: End date for filed_at range (defaults to today)
        """
        to_date = to_date or date.today()

        # Build query string
        if len(ciks) > 1:
            cik_query = f"cik:({', '.join(ciks)})"
        else:
            cik_query = f"cik:{ciks[0]}"

        form_query = " OR ".join([f'formType:"{ft}"' for ft in form_types])
        date_query = f"filedAt:[{from_date.isoformat()} TO {to_date.isoformat()}]"

        query = f"({cik_query}) AND ({form_query}) AND {date_query}"
        logger.info(f"Searching SEC filings with query: {query}")

        all_filings = []
        offset = 0

        while True:
            try:
                response = await self._client.post(
                    self.QUERY_API_URL,
                    json={
                        "query": query,
                        "from": str(offset),
                        "size": str(self.MAX_PAGE_SIZE),
                        "sort": [{"filedAt": {"order": "desc"}}]
                    }
                )

                if response.status_code == 429:
                    raise APIRateLimitError(retry_after=60)
                if response.status_code == 401:
                    raise APIAuthenticationError("Invalid API key")

                response.raise_for_status()
                data = response.json()

                filings = data.get("filings", [])
                for filing in filings:
                    all_filings.append(self._parse_filing(filing))

                # Check if we have more pages
                total = data.get("total", {}).get("value", 0)
                offset += len(filings)

                logger.info(f"Retrieved {len(filings)} filings (total: {offset}/{total})")

                if offset >= total or len(filings) < self.MAX_PAGE_SIZE:
                    break

            except httpx.RequestError as e:
                raise APIConnectionError(f"Failed to connect to SEC API: {e}")

        return all_filings

    async def get_company_info(self, cik: str) -> Optional[dict]:
        """
        Get company information for a CIK.
        Uses a minimal query to retrieve company name and ticker.
        """
        try:
            response = await self._client.post(
                self.QUERY_API_URL,
                json={
                    "query": f"cik:{cik}",
                    "from": "0",
                    "size": "1"
                }
            )
            response.raise_for_status()
            data = response.json()

            filings = data.get("filings", [])
            if filings:
                return {
                    "name": filings[0].get("companyName", ""),
                    "ticker": filings[0].get("ticker", ""),
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to get company info for CIK {cik}: {e}")
            return None

    def _parse_filing(self, data: dict) -> SECFiling:
        """Parse raw API response into SECFiling dataclass"""
        filed_at_str = data.get("filedAt", "")
        try:
            # Handle various datetime formats
            if filed_at_str.endswith("Z"):
                filed_at_str = filed_at_str.replace("Z", "+00:00")
            filed_at = datetime.fromisoformat(filed_at_str)
        except ValueError:
            filed_at = datetime.now()

        return SECFiling(
            accession_number=data.get("accessionNo", ""),
            form_type=data.get("formType", ""),
            filed_at=filed_at,
            company_name=data.get("companyName", ""),
            cik=data.get("cik", ""),
            ticker=data.get("ticker"),
            document_files=data.get("documentFormatFiles", []),
            period_of_report=self._parse_date(data.get("periodOfReport"))
        )

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def build_download_url(self, cik: str, accession_number: str, filename: str) -> str:
        """
        Build the download URL for a specific document.

        Args:
            cik: CIK without leading zeros
            accession_number: Accession number (hyphens will be removed)
            filename: The specific file to download
        """
        # Remove hyphens from accession number for URL
        accession_clean = accession_number.replace("-", "")
        return f"{self.DOWNLOAD_API_URL}/{cik}/{accession_clean}/{filename}"

    async def download_document(self, url: str) -> bytes:
        """Download a document from the archive API"""
        try:
            response = await self._client.get(url)
            if response.status_code == 429:
                raise APIRateLimitError(retry_after=60)
            response.raise_for_status()
            return response.content
        except httpx.RequestError as e:
            raise APIConnectionError(f"Failed to download document: {e}")
