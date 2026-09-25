"""Fire-and-forget recording of scrape outcomes."""

import logging
from datetime import datetime, timezone

from app.models.scrape_event import ScrapeEvent

logger = logging.getLogger(__name__)


async def record_scrape_event(session_factory, *, site: str, url_kind: str, verdict: str, proxy_label: str | None, duration_ms: int) -> None:
    """Insert one row in its own transaction. Never raises — telemetry must not break scraping."""
    try:
        async with session_factory() as db:
            db.add(ScrapeEvent(time=datetime.now(timezone.utc), site=site, url_kind=url_kind, verdict=verdict,
                               proxy_label=proxy_label, duration_ms=duration_ms))
            await db.commit()
    except Exception as e:
        logger.debug("scrape event not recorded: %s", e)
