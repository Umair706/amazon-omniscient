"""Quick test of the new scraping methods: autocomplete, SERP metadata, stock level."""

import asyncio
import json
import sys
import time


async def test_autocomplete():
    """Test Amazon autocomplete API (no Playwright, just httpx)."""
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 60)
    print("TEST 1: Amazon Autocomplete API")
    print("=" * 60)

    scraper = ScraperService(marketplace="AU")

    test_queries = ["baby silicone bibs", "silicone bib"]
    for query in test_queries:
        print(f"\n  Query: '{query}'")
        start = time.time()
        results = await scraper.fetch_autocomplete(query)
        elapsed = time.time() - start
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Results ({len(results)}):")
        for i, r in enumerate(results[:8]):
            print(f"    {i+1}. {r}")
        if len(results) > 8:
            print(f"    ... and {len(results) - 8} more")

    # Test alphabet expansion
    print(f"\n  Alphabet expansion: 'baby silicone bibs a'")
    start = time.time()
    results_a = await scraper.fetch_autocomplete("baby silicone bibs a")
    elapsed = time.time() - start
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Results ({len(results_a)}):")
    for i, r in enumerate(results_a[:5]):
        print(f"    {i+1}. {r}")

    return len(results) > 0


async def test_serp_metadata():
    """Test SERP metadata scraping (Playwright)."""
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 60)
    print("TEST 2: SERP Metadata Scraping")
    print("=" * 60)

    scraper = ScraperService(marketplace="AU")

    keyword = "baby silicone bibs"
    print(f"\n  Keyword: '{keyword}'")
    start = time.time()
    result = await scraper.scrape_serp_metadata(keyword)
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Result:")
    print(f"    Total results:  {result.get('total_result_count', 0):,}")
    print(f"    Sponsored ads:  {result.get('sponsored_count', 0)}")
    print(f"    Unique brands:  {result.get('brand_count', 0)}")

    # Volume estimation
    from app.services.keyword_research import KeywordResearchService
    volume_data = KeywordResearchService.estimate_volume_from_serp(result)
    print(f"\n  Volume Estimation:")
    print(f"    Est. volume:    {volume_data['volume_estimate']:,}")
    print(f"    Tier:           {volume_data['tier']}")
    print(f"    Est. CPC:       ${volume_data['estimated_cpc']:.2f}")

    return True


async def test_stock_level():
    """Test stock level scraping from a product page."""
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 60)
    print("TEST 3: Stock Level Scraping")
    print("=" * 60)

    scraper = ScraperService(marketplace="AU")

    # Use a known AU ASIN for baby bibs
    asin = "B09VKYDGK1"
    print(f"\n  ASIN: {asin}")
    start = time.time()
    result = await scraper.scrape_stock_level(asin)
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Result:")
    print(f"    Stock level:  {result.get('stock_level')}")
    print(f"    Stock text:   {(result.get('stock_text') or '')[:80]}")
    print(f"    In stock:     {result.get('is_in_stock')}")

    return True


async def test_full_autocomplete_discovery():
    """Test the full autocomplete keyword discovery (all letters)."""
    from app.services.keyword_research import KeywordResearchService
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 60)
    print("TEST 4: Full Autocomplete Discovery (a-z expansion)")
    print("=" * 60)

    scraper = ScraperService(marketplace="AU")
    # Pass None for session since we're not saving to DB
    service = KeywordResearchService(session=None, scraper=scraper, marketplace="AU")

    seed = "baby silicone bibs"
    print(f"\n  Seed keyword: '{seed}'")
    start = time.time()
    discovered = await service.discover_keywords_autocomplete(seed, max_variations=50)
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Total discovered: {len(discovered)}")
    print(f"\n  Top 15 keywords:")
    for i, kw in enumerate(discovered[:15]):
        print(f"    {i+1:2d}. {kw['keyword']:<50s} (depth={kw['autocomplete_depth']})")

    return len(discovered) > 0


async def main():
    print("=" * 60)
    print("  SCRAPING FEATURE TESTS")
    print("=" * 60)

    results = {}

    # Test 1: Autocomplete (fastest, no Playwright)
    try:
        results["autocomplete"] = await test_autocomplete()
    except Exception as e:
        print(f"\n  FAILED: {e}")
        results["autocomplete"] = False

    # Test 2: SERP metadata (Playwright)
    try:
        results["serp_metadata"] = await test_serp_metadata()
    except Exception as e:
        print(f"\n  FAILED: {e}")
        results["serp_metadata"] = False

    # Test 3: Stock level (Playwright)
    try:
        results["stock_level"] = await test_stock_level()
    except Exception as e:
        print(f"\n  FAILED: {e}")
        results["stock_level"] = False

    # Test 4: Full discovery
    try:
        results["discovery"] = await test_full_autocomplete_discovery()
    except Exception as e:
        print(f"\n  FAILED: {e}")
        results["discovery"] = False

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test_name}")
    print("=" * 60)

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
