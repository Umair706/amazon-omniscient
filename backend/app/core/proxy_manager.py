"""Rotating proxy manager for web scraping."""

import random
import string
from dataclasses import dataclass, field


@dataclass
class ProxyConfig:
    server: str
    username: str
    password: str


class ProxyManager:
    """
    Manages rotating residential proxies.
    Supports BrightData and SmartProxy URL formats.

    BrightData session format:
      http://{username}-session-{random}:{password}@{host}:{port}

    SmartProxy format:
      http://{username}:{password}@{host}:{port}
    """

    def __init__(
        self,
        provider: str,
        host: str,
        port: str,
        username: str,
        password: str,
    ):
        self.provider = provider.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._failed: set[str] = set()
        self._usage_count: int = 0

    def _random_session_id(self, length: int = 8) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def get_next(self) -> ProxyConfig:
        """
        Get the next proxy configuration with a fresh session.
        Each call generates a new session ID for IP rotation.
        """
        self._usage_count += 1
        session_id = self._random_session_id()

        if self.provider == "brightdata":
            proxy_username = f"{self.username}-session-{session_id}"
            server = f"http://{self.host}:{self.port}"
            return ProxyConfig(
                server=server,
                username=proxy_username,
                password=self.password,
            )

        elif self.provider == "smartproxy":
            server = f"http://{self.host}:{self.port}"
            return ProxyConfig(
                server=server,
                username=self.username,
                password=self.password,
            )

        else:
            # Generic proxy format
            server = f"http://{self.host}:{self.port}"
            return ProxyConfig(
                server=server,
                username=self.username,
                password=self.password,
            )

    def get_playwright_proxy(self) -> dict:
        """Get proxy config formatted for Playwright browser launch."""
        config = self.get_next()
        return {
            "server": config.server,
            "username": config.username,
            "password": config.password,
        }

    def mark_failed(self, session_id: str) -> None:
        """Mark a proxy session as failed for tracking."""
        self._failed.add(session_id)

    @property
    def usage_count(self) -> int:
        return self._usage_count

    @property
    def failure_count(self) -> int:
        return len(self._failed)
