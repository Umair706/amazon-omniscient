"""Custom exception classes for the Omniscient application."""


class OmniscientError(Exception):
    """Base exception for all Omniscient errors."""

    def __init__(self, detail: str, status_code: int = 500, retry_after: int | None = None):
        self.detail = detail
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(detail)


class ScrapingError(OmniscientError):
    """Raised when web scraping fails."""

    def __init__(self, detail: str, retry_after: int | None = 30):
        super().__init__(detail, status_code=502, retry_after=retry_after)


class WrongMarketplaceError(ScrapingError):
    """Amazon redirected us to another country's store.

    Retrying cannot help: the redirect is decided by the exit IP's country, so the
    operator must change the proxy or use SP-API. Callers must not retry on this.
    """

    def __init__(self, detail: str):
        super().__init__(detail, retry_after=None)


class SPAPIError(OmniscientError):
    """Raised when Amazon SP-API calls fail."""

    def __init__(self, detail: str, retry_after: int | None = None):
        super().__init__(detail, status_code=502, retry_after=retry_after)


class SupplierAPIError(OmniscientError):
    """Raised when Alibaba/supplier API calls fail."""

    def __init__(self, detail: str):
        super().__init__(detail, status_code=502)


class LLMError(OmniscientError):
    """Raised when LLM provider calls fail."""

    def __init__(self, detail: str, retry_after: int | None = None):
        super().__init__(detail, status_code=502, retry_after=retry_after)


class RateLimitExceeded(OmniscientError):
    """Raised when a rate limit is hit."""

    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(detail, status_code=429, retry_after=retry_after)


class EncryptionError(OmniscientError):
    """Raised when encryption/decryption fails."""

    def __init__(self, detail: str = "Encryption operation failed"):
        super().__init__(detail, status_code=500)


class DataValidationError(OmniscientError):
    """Raised when data validation fails."""

    def __init__(self, detail: str):
        super().__init__(detail, status_code=422)
