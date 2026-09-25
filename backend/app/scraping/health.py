"""Turn scrape_events rows into the /scrape-health response shape.

WHY a separate pure function: the aggregation itself (grouping counts by verdict)
has no dependency on a live database, so it can be unit-tested without one. The
endpoint stays a thin wrapper: run the query, hand the rows here.
"""

# How far back the health endpoint looks. 24h is long enough to catch a slow
# block-rate creep but short enough that a fixed problem clears the dashboard fast.
SCRAPE_HEALTH_WINDOW_HOURS = 24


def summarise_scrape_counts(rows: list[tuple[str, str, int]]) -> dict:
    """Group (site, verdict, count) rows into {"counts": [...]}."""
    return {
        "counts": [
            {"site": site, "verdict": verdict, "count": count}
            for site, verdict, count in rows
        ]
    }
