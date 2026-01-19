"""Custom exceptions for SEC filing operations"""


class SECFilingError(Exception):
    """Base exception for SEC filing operations"""
    pass


class APIConnectionError(SECFilingError):
    """Failed to connect to SEC API"""
    pass


class APIAuthenticationError(SECFilingError):
    """API key invalid or expired"""
    pass


class APIRateLimitError(SECFilingError):
    """Rate limit exceeded"""
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class DocumentDownloadError(SECFilingError):
    """Failed to download a document"""
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to download {url}: {reason}")


class StorageError(SECFilingError):
    """Failed to save document to disk"""
    pass
