"""Rotating proxy manager for web scraping.

Supports three modes:
  - ``none``       Direct connection, no proxy (default for development).
  - ``free``       Fetch free HTTPS proxies from public lists and rotate.
  - ``brightdata`` / ``smartproxy``  Paid residential proxy services.
"""

import logging
import random
import string
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_FREE_PROXY_URL = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get"
    "?request=display_proxies"
    "&proxy_format=protocolipport"
    "&format=text"
    "&timeout=5000"
)


@dataclass
class ProxyConfig:
    server: str
    username: str
    password: str


class ProxyManager:
    """Manages rotating proxies for web scraping.

    Modes
    -----
    ``none`` (or empty string)
        No proxy is used.  ``get_next()`` returns an empty
        ``ProxyConfig`` and ``get_playwright_proxy()`` returns ``{}``.

    ``free``
        On the first ``get_next()`` call the manager fetches a list of
        free HTTPS proxies from a public API, caches them, and rotates
        through the list.  Failed proxies are tracked and skipped.
        If the fetch fails the manager silently falls back to *none* mode.

    ``brightdata``
        BrightData session format:
        ``http://{username}-session-{random}:{password}@{host}:{port}``

    ``smartproxy``
        SmartProxy format:
        ``http://{username}:{password}@{host}:{port}``
    """

    def __init__(
        self,
        provider: str = "none",
        host: str = "",
        port: str = "",
        username: str = "",
        password: str = "",
    ):
        self.provider = (provider or "none").strip().lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password

        # Free-proxy state
        self._free_proxies: list[str] = []
        self._free_index: int = 0
        self._free_fetched: bool = False

        # Tracking
        self._failed: set[str] = set()
        self._usage_count: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _random_session_id(self, length: int = 8) -> str:
        return "".join(
            random.choices(string.ascii_lowercase + string.digits, k=length)
        )

    def _fetch_free_proxies(self) -> list[str]:
        """Synchronously fetch free proxy list via httpx.

        Returns a list of proxy URLs (e.g. ``["http://1.2.3.4:8080", ...]``).
        On failure returns an empty list.
        """
        try:
            logger.info("Fetching free proxy list from proxyscrape...")
            resp = httpx.get(_FREE_PROXY_URL, timeout=15.0)
            resp.raise_for_status()
            lines = [
                line.strip()
                for line in resp.text.splitlines()
                if line.strip()
            ]
            # Each line is already in protocol://ip:port format
            # Ensure they all start with http:// or https://
            proxies: list[str] = []
            for line in lines:
                if line.startswith("http://") or line.startswith("https://"):
                    proxies.append(line)
                else:
                    # Bare ip:port -- assume http
                    proxies.append(f"http://{line}")
            random.shuffle(proxies)
            logger.info("Fetched %d free proxies.", len(proxies))
            return proxies
        except Exception as exc:
            logger.warning(
                "Failed to fetch free proxy list, falling back to no-proxy mode: %s",
                exc,
            )
            return []

    def _ensure_free_proxies(self) -> None:
        """Lazy-load the free proxy list on first use."""
        if self._free_fetched:
            return
        self._free_fetched = True
        self._free_proxies = self._fetch_free_proxies()
        self._free_index = 0

    def _next_free_proxy(self) -> ProxyConfig:
        """Rotate through the cached free proxy list, skipping failed ones."""
        self._ensure_free_proxies()

        if not self._free_proxies:
            # Fetch returned nothing -- fall back to direct connection
            logger.warning("No free proxies available, using direct connection.")
            return ProxyConfig(server="", username="", password="")

        # Try to find a non-failed proxy, cycling at most once through the list
        attempts = len(self._free_proxies)
        for _ in range(attempts):
            proxy_url = self._free_proxies[self._free_index % len(self._free_proxies)]
            self._free_index += 1
            if proxy_url not in self._failed:
                return ProxyConfig(
                    server=proxy_url, username="", password=""
                )

        # All proxies have been marked as failed -- refresh and try once more
        logger.warning(
            "All %d free proxies marked as failed, refreshing list...",
            len(self._free_proxies),
        )
        self.refresh_proxies()
        if self._free_proxies:
            proxy_url = self._free_proxies[0]
            self._free_index = 1
            return ProxyConfig(server=proxy_url, username="", password="")

        return ProxyConfig(server="", username="", password="")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def has_proxy(self) -> bool:
        """Return ``True`` if a proxy is configured (i.e. not *none* mode)."""
        if self.provider == "none":
            return False
        if self.provider == "free":
            # We report True even before fetching; the actual get_next()
            # may fall back to direct if the fetch fails, but the intent is
            # to use a proxy.
            return True
        # brightdata / smartproxy / generic -- proxy is configured when
        # host is set.
        return bool(self.host)

    def get_next(self) -> ProxyConfig:
        """Return the next proxy configuration.

        For *none* mode an empty ``ProxyConfig`` is returned.
        For *free* mode a rotating free proxy is returned.
        For paid providers a session-rotated proxy is returned.
        """
        self._usage_count += 1

        if self.provider == "none":
            return ProxyConfig(server="", username="", password="")

        if self.provider == "free":
            return self._next_free_proxy()

        # --- Paid providers ---
        session_id = self._random_session_id()

        if self.provider == "brightdata":
            proxy_username = f"{self.username}-session-{session_id}"
            server = f"http://{self.host}:{self.port}"
            return ProxyConfig(
                server=server,
                username=proxy_username,
                password=self.password,
            )

        if self.provider == "smartproxy":
            server = f"http://{self.host}:{self.port}"
            return ProxyConfig(
                server=server,
                username=self.username,
                password=self.password,
            )

        # Generic proxy format (fallback)
        server = f"http://{self.host}:{self.port}"
        return ProxyConfig(
            server=server,
            username=self.username,
            password=self.password,
        )

    def get_playwright_proxy(self) -> dict:
        """Return proxy config formatted for Playwright browser launch.

        For *none* mode (or when no proxy is available) returns an empty
        dict so Playwright uses a direct connection.
        """
        if not self.has_proxy:
            return {}

        config = self.get_next()

        # If the config came back empty (e.g. free-proxy fallback), return {}
        if not config.server:
            return {}

        proxy_dict: dict = {"server": config.server}
        if config.username:
            proxy_dict["username"] = config.username
        if config.password:
            proxy_dict["password"] = config.password
        return proxy_dict

    def refresh_proxies(self) -> None:
        """Re-fetch the free proxy list and clear failure tracking.

        Only meaningful for ``free`` mode; a no-op for other providers.
        """
        if self.provider != "free":
            return
        self._failed.clear()
        self._free_fetched = False
        self._free_proxies.clear()
        self._free_index = 0
        self._ensure_free_proxies()

    def mark_failed(self, proxy_or_session: str) -> None:
        """Mark a proxy (URL) or session ID as failed for tracking."""
        self._failed.add(proxy_or_session)

    @property
    def usage_count(self) -> int:
        return self._usage_count

    @property
    def failure_count(self) -> int:
        return len(self._failed)
