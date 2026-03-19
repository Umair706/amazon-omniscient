"""Test the new enriched product page scraping fields."""

import asyncio
import json
import sys
import time


async def test_enriched_product_page():
    """Test all new enriched fields from a product page scrape."""
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 70)
    print("TEST: Enriched Product Page Scraping")
    print("=" * 70)

    # Test with AU marketplace (works without proxies)
    scraper = ScraperService(marketplace="AU")

    # Use a valid AU product (discovered from search)
    asin = "B0CJ8S9Q72"  # PandaEar Silicone Baby Bibs
    print(f"\n  ASIN: {asin} (AU marketplace)")
    start = time.time()
    result = await scraper.scrape_product_page(asin)
    elapsed = time.time() - start

    print(f"  Scrape time: {elapsed:.2f}s")
    print(f"\n  ── Basic Fields ──")
    print(f"    Title:          {(result.get('title') or '')[:70]}")
    print(f"    Price:          ${result.get('price') or 'N/A'}")
    print(f"    Rating:         {result.get('rating')}")
    print(f"    Reviews:        {result.get('review_count')}")
    print(f"    Brand:          {result.get('brand')}")
    print(f"    BSR:            {result.get('current_bsr')}")

    print(f"\n  ── NEW: Pricing ──")
    print(f"    List Price:     ${result.get('list_price') or 'N/A'}")
    print(f"    Current Price:  ${result.get('price') or 'N/A'}")
    if result.get('list_price') and result.get('price'):
        discount = ((result['list_price'] - result['price']) / result['list_price']) * 100
        print(f"    Discount:       {discount:.1f}%")

    print(f"\n  ── NEW: Dimensions & Weight ──")
    print(f"    Dimensions:     {result.get('dimensions') or 'N/A'}")
    print(f"    Weight:         {result.get('weight') or 'N/A'}")
    print(f"    Date First Available: {result.get('date_first_available') or 'N/A'}")

    print(f"\n  ── NEW: Star Distribution ──")
    star_dist = result.get('star_distribution')
    if star_dist:
        for stars in range(5, 0, -1):
            pct = star_dist.get(f"{stars}_star", 0)
            bar = "█" * (pct // 2) if pct else ""
            print(f"    {stars}★: {pct:3d}% {bar}")
    else:
        print(f"    Not available")

    print(f"\n  ── NEW: Variations ──")
    print(f"    Variation count: {result.get('variation_count') or 'N/A'}")

    print(f"\n  ── NEW: Category ──")
    print(f"    Category path:  {result.get('category_path') or 'N/A'}")

    print(f"\n  ── NEW: Sellers ──")
    print(f"    Seller count:   {result.get('seller_count') or 'N/A'}")

    print(f"\n  ── NEW: Frequently Bought Together ──")
    fbt = result.get('fbt_asins', [])
    print(f"    FBT ASINs ({len(fbt)}): {', '.join(fbt) if fbt else 'None'}")

    print(f"\n  ── NEW: Q&A ──")
    print(f"    Q&A Count:      {result.get('qa_count') or 'N/A'}")

    print(f"\n  ── NEW: Deal Badge ──")
    print(f"    Deal badge:     {result.get('deal_badge') or 'None'}")

    print(f"\n  ── NEW: Amazon's Choice ──")
    print(f"    AC keyword:     {result.get('amazons_choice_keyword') or 'N/A'}")

    print(f"\n  ── NEW: Review Attributes ──")
    attrs = result.get('review_attributes')
    if attrs:
        for attr in attrs:
            print(f"    {attr['attribute']:20s} {attr['percentage']:>5s}  ({attr['sentiment']})")
    else:
        print(f"    Not available")

    print(f"\n  ── NEW: Comparison ASINs ──")
    comp = result.get('comparison_asins', [])
    print(f"    Comparison ({len(comp)}): {', '.join(comp) if comp else 'None'}")

    print(f"\n  ── Existing Fields ──")
    print(f"    Stock level:    {result.get('stock_level')}")
    print(f"    Stock text:     {(result.get('stock_text') or '')[:60]}")
    print(f"    In stock:       {result.get('is_in_stock')}")
    print(f"    Coupon:         {result.get('coupon') or 'None'}")
    print(f"    Subscribe&Save: {result.get('subscribe_save')}")

    # Count how many new fields have data
    new_fields = [
        'list_price', 'dimensions', 'weight', 'date_first_available',
        'star_distribution', 'variation_count', 'category_path',
        'seller_count', 'fbt_asins', 'qa_count', 'deal_badge',
        'amazons_choice_keyword', 'review_attributes', 'comparison_asins',
    ]
    populated = sum(1 for f in new_fields if result.get(f))
    print(f"\n  ── SUMMARY ──")
    print(f"    New fields populated: {populated}/{len(new_fields)}")

    return result


async def test_second_product():
    """Test with a second product to validate robustness."""
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 70)
    print("TEST 2: Second Product (different category)")
    print("=" * 70)

    scraper = ScraperService(marketplace="AU")
    asin = "B0C6KHVS4D"  # A different AU product (not PandaEar)
    print(f"\n  ASIN: {asin}")
    start = time.time()
    result = await scraper.scrape_product_page(asin)
    elapsed = time.time() - start

    print(f"  Scrape time: {elapsed:.2f}s")
    print(f"    Title:           {(result.get('title') or '')[:70]}")
    print(f"    Price:           ${result.get('price') or 'N/A'}")
    print(f"    List Price:      ${result.get('list_price') or 'N/A'}")
    print(f"    Dimensions:      {result.get('dimensions') or 'N/A'}")
    print(f"    Weight:          {result.get('weight') or 'N/A'}")
    print(f"    Date First:      {result.get('date_first_available') or 'N/A'}")
    star_dist = result.get('star_distribution')
    if star_dist:
        print(f"    Star dist:       5★={star_dist.get('5_star',0)}% 4★={star_dist.get('4_star',0)}% 3★={star_dist.get('3_star',0)}% 2★={star_dist.get('2_star',0)}% 1★={star_dist.get('1_star',0)}%")
    print(f"    Variations:      {result.get('variation_count') or 'N/A'}")
    print(f"    Category path:   {result.get('category_path') or 'N/A'}")
    print(f"    Seller count:    {result.get('seller_count') or 'N/A'}")
    print(f"    FBT ASINs:       {len(result.get('fbt_asins', []))}")
    print(f"    Q&A Count:       {result.get('qa_count') or 'N/A'}")
    print(f"    Review attrs:    {len(result.get('review_attributes') or [])}")

    new_fields = [
        'list_price', 'dimensions', 'weight', 'date_first_available',
        'star_distribution', 'variation_count', 'category_path',
        'seller_count', 'fbt_asins', 'qa_count', 'deal_badge',
        'amazons_choice_keyword', 'review_attributes', 'comparison_asins',
    ]
    populated = sum(1 for f in new_fields if result.get(f))
    print(f"    New fields populated: {populated}/{len(new_fields)}")

    return result


async def test_search_position():
    """Test that search results include organic position."""
    from app.services.scraper_service import ScraperService

    print("\n" + "=" * 70)
    print("TEST 3: Search Results — Organic Position Tracking")
    print("=" * 70)

    scraper = ScraperService(marketplace="AU")
    keyword = "baby silicone bibs"
    print(f"\n  Keyword: '{keyword}' (AU marketplace)")
    start = time.time()
    results = await scraper.scrape_search_results(keyword, pages=1)
    elapsed = time.time() - start

    print(f"  Scrape time: {elapsed:.2f}s")
    print(f"  Results found: {len(results)}")

    if not results:
        print("  WARNING: No search results returned!")
        return []

    # Show first 10 results with position
    print(f"\n  ── Top Results ──")
    organic_count = 0
    sponsored_count = 0
    for r in results[:15]:
        pos = r.get("position", "?")
        asin = r.get("asin", "?")
        title = (r.get("title") or "")[:50]
        price = r.get("price")
        is_spons = r.get("is_sponsored", False)
        is_ac = r.get("is_amazon_choice", False)
        is_bs = r.get("is_best_seller", False)

        badges = []
        if is_spons:
            badges.append("SP")
            sponsored_count += 1
        else:
            organic_count += 1
        if is_ac:
            badges.append("AC")
        if is_bs:
            badges.append("BS")
        badge_str = f" [{','.join(badges)}]" if badges else ""

        price_str = f"${price}" if price else "N/A"
        print(f"    #{pos:>2} {asin} {price_str:>8}  {title}{badge_str}")

    print(f"\n  ── SUMMARY ──")
    print(f"    Total results: {len(results)}")
    print(f"    Organic:       {organic_count} (of first 15)")
    print(f"    Sponsored:     {sponsored_count} (of first 15)")
    has_positions = sum(1 for r in results if r.get("position") is not None)
    print(f"    With position: {has_positions}/{len(results)}")

    return results


async def main():
    print("=" * 70)
    print("  ENRICHED SCRAPING TESTS")
    print("=" * 70)

    results = {}

    try:
        result1 = await test_enriched_product_page()
        results["product_1"] = True
    except Exception as e:
        print(f"\n  FAILED: {e}")
        import traceback
        traceback.print_exc()
        results["product_1"] = False

    try:
        result2 = await test_second_product()
        results["product_2"] = True
    except Exception as e:
        print(f"\n  FAILED: {e}")
        import traceback
        traceback.print_exc()
        results["product_2"] = False

    try:
        result3 = await test_search_position()
        results["search_position"] = len(result3) > 0
    except Exception as e:
        print(f"\n  FAILED: {e}")
        import traceback
        traceback.print_exc()
        results["search_position"] = False

    # Summary
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    print("=" * 70)

    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    asyncio.run(main())
