"""Manage browser cookies for authenticated scraping sessions."""

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class CookieManager:
    """Persist and retrieve Playwright browser storage state (cookies + localStorage).

    Storage state files are saved as JSON on disk, one per site. They can be
    passed directly to ``browser.new_context(storage_state=...)`` for
    authenticated sessions.
    """

    def __init__(self, cookies_dir: str = "/app/data/cookies"):
        self.cookies_dir = Path(cookies_dir)
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def get_storage_path(self, site: str) -> Path:
        """Return the path to the storage state file for *site*."""
        return self.cookies_dir / f"{site}_cookies.json"

    def has_valid_cookies(self, site: str, max_age_hours: int = 12) -> bool:
        """Check if cookies exist and aren't too old."""
        path = self.get_storage_path(site)
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        return age < max_age_hours * 3600

    def get_storage_state(self, site: str) -> str | None:
        """Return path to storage state file for Playwright, or ``None``."""
        path = self.get_storage_path(site)
        return str(path) if path.exists() else None

    async def save_storage_state(self, context, site: str) -> None:
        """Save browser context storage state (cookies + localStorage)."""
        path = self.get_storage_path(site)
        await context.storage_state(path=str(path))
        logger.info("Saved cookies for %s to %s", site, path)
