"""One coherent browser identity per scraping session.

WHY: Amazon scores mismatches (a macOS user-agent on a Linux Chromium, en-US
headers on amazon.com.au). Every value here is derived from one choice so they agree.
"""

import random
from dataclasses import dataclass

from app.core.marketplace import MarketplaceConfig

_PLATFORMS = [
    # (UA platform token, navigator.platform)
    ("Windows NT 10.0; Win64; x64", "Win32"),
    ("Macintosh; Intel Mac OS X 10_15_7", "MacIntel"),
]
_VIEWPORTS = [(1366, 768), (1440, 900), (1536, 864), (1920, 1080)]


@dataclass(frozen=True)
class Persona:
    user_agent: str
    platform: str
    viewport: dict
    locale: str
    timezone_id: str
    accept_language: str

    def init_script(self) -> str:
        """JS run before any page script; hides automation markers and aligns navigator.platform."""
        return f"""
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
            Object.defineProperty(navigator, 'platform', {{get: () => '{self.platform}'}});
            Object.defineProperty(navigator, 'languages', {{get: () => ['{self.locale}', 'en']}});
            window.chrome = window.chrome || {{ runtime: {{}} }};
        """


def build_persona(chromium_version: str, marketplace: MarketplaceConfig) -> Persona:
    """Pick a platform + viewport and derive every other value from it and the marketplace."""
    ua_platform, nav_platform = random.choice(_PLATFORMS)
    major = chromium_version.split(".")[0]
    width, height = random.choice(_VIEWPORTS)
    return Persona(
        user_agent=(
            f"Mozilla/5.0 ({ua_platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{major}.0.0.0 Safari/537.36"
        ),
        platform=nav_platform,
        viewport={"width": width, "height": height},
        locale=marketplace.locale,
        timezone_id=marketplace.timezone,
        accept_language=f"{marketplace.locale},en;q=0.9",
    )
