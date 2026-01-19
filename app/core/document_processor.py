"""Document naming and storage handling"""

import re
from pathlib import Path
from datetime import date
from typing import Optional
import logging

from app.core.sec_client import SECFiling

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document naming and storage"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def generate_filename(
        self,
        fund_name: str,
        ticker: Optional[str],
        reporting_date: Optional[date],
        form_type: str,
        extension: str = "html"
    ) -> str:
        """
        Generate filename: [Name of fund]-[ticker]-[reporting date].[ext]

        Falls back gracefully when data is missing.
        """
        # Sanitize fund name
        safe_name = self._sanitize_filename(fund_name)

        # Build parts
        parts = [safe_name]

        if ticker:
            parts.append(ticker.upper())

        if reporting_date:
            parts.append(reporting_date.strftime("%Y-%m-%d"))
        else:
            parts.append("unknown-date")

        parts.append(form_type)

        filename = "-".join(parts)
        return f"{filename}.{extension}"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Remove or replace characters invalid in filenames"""
        # Replace common problematic characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        # Remove any other non-alphanumeric except underscore and hyphen
        sanitized = re.sub(r'[^\w\-]', '', sanitized)
        return sanitized[:100]  # Limit length

    def save_document(
        self,
        content: bytes,
        filename: str,
        subfolder: Optional[str] = None
    ) -> tuple[str, int]:
        """
        Save document to disk.

        Returns:
            tuple of (full_path, file_size_bytes)
        """
        save_dir = self.base_path
        if subfolder:
            save_dir = save_dir / self._sanitize_filename(subfolder)
            save_dir.mkdir(parents=True, exist_ok=True)

        file_path = save_dir / filename

        # Handle duplicate filenames
        counter = 1
        original_stem = file_path.stem
        suffix = file_path.suffix
        while file_path.exists():
            file_path = save_dir / f"{original_stem}_{counter}{suffix}"
            counter += 1

        file_path.write_bytes(content)
        logger.info(f"Saved document to {file_path}")

        return str(file_path), len(content)

    def find_primary_document(self, filing: SECFiling) -> Optional[dict]:
        """Find the primary document (usually the HTML filing) from document list"""
        if not filing.document_files:
            return None

        # Look for the primary document based on form type naming
        for doc in filing.document_files:
            doc_url = doc.get("documentUrl", "").lower()
            # N-CSR primary documents typically contain the form type in name
            if any(x in doc_url for x in ["n-csr", "ncsr"]):
                if doc_url.endswith((".htm", ".html")):
                    return doc

        # Fallback: look for primary_doc designation
        for doc in filing.document_files:
            if doc.get("type", "").upper() in ["N-CSR", "N-CSRS", "PRIMARY_DOC"]:
                return doc

        # Next fallback: first HTML document
        for doc in filing.document_files:
            doc_url = doc.get("documentUrl", "").lower()
            if doc_url.endswith((".htm", ".html")):
                return doc

        # Last resort: first document
        return filing.document_files[0]

    def get_file_extension(self, document: dict) -> str:
        """Extract file extension from document info"""
        doc_url = document.get("documentUrl", "")
        if "." in doc_url:
            ext = doc_url.rsplit(".", 1)[-1].lower()
            if ext in ["htm", "html", "xml", "txt", "pdf"]:
                return ext
        return "html"
