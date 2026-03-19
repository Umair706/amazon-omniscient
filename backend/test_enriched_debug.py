"""Debug test: deeper check of histogram and AC badge."""

import asyncio
from playwright.async_api import async_playwright


async def main():
    asin = "B0CJ8S9Q72"

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1400, "height": 900},
        locale="en-AU",
        timezone_id="Australia/Sydney",
        ignore_https_errors=True,
    )
    page = await context.new_page()
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
    """)

    url = f"https://www.amazon.com.au/dp/{asin}"
    print(f"Loading: {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)

    # ── Histogram deep debug ──
    print("\n=== HISTOGRAM DEBUG ===")

    # Try to get all links with star ratings
    star_links = page.locator('#histogramTable a, #reviewsMedley a[title*="star"]')
    count = await star_links.count()
    print(f"Star links found: {count}")
    for i in range(count):
        el = star_links.nth(i)
        title = await el.get_attribute("title") or ""
        text = (await el.inner_text()).strip()
        href = await el.get_attribute("href") or ""
        if "star" in title.lower() or "star" in text.lower():
            print(f"  [{i}] title='{title}' text='{text}' href='{href[:50]}'")

    # Try histogram rows
    hist_rows = page.locator('#histogramTable tr, .cr-widget-FocalCustomerReviews tr')
    rcount = await hist_rows.count()
    print(f"\nHistogram rows: {rcount}")
    for i in range(min(rcount, 10)):
        row = hist_rows.nth(i)
        text = (await row.inner_text()).strip()
        if text:
            print(f"  Row {i}: {text[:100]}")

    # ── AC Badge debug ──
    print("\n=== AMAZON'S CHOICE DEBUG ===")
    ac_div = page.locator("#acBadge_feature_div")
    if await ac_div.count():
        ac_html = await ac_div.inner_html()
        print(f"AC HTML: {ac_html[:500]}")
        ac_text = await ac_div.inner_text()
        print(f"AC text: {ac_text[:200]}")

    # Try various AC keyword selectors
    for sel in (
        '#acBadge_feature_div .ac-keyword-link',
        '#acBadge_feature_div span.ac-keyword-link',
        '#acBadge_feature_div .ac-badge-popover-info',
        '#acBadge_feature_div span[class*="keyword"]',
        '#acBadge_feature_div a',
    ):
        el = page.locator(sel)
        cnt = await el.count()
        if cnt:
            text = await el.first.inner_text()
            print(f"  AC selector '{sel}': '{text}'")

    # ── Detail bullets raw ──
    print("\n=== DETAIL BULLETS RAW ===")
    detail = page.locator("#detailBulletsWrapper_feature_div, #productDetails_detailBullets_sections1")
    if await detail.count():
        html = await detail.first.inner_html()
        print(html[:1000])

    # ── Breadcrumb alternatives ──
    print("\n=== BREADCRUMB ALTERNATIVES ===")
    for sel in (
        "#wayfinding-breadcrumbs_container",
        "#wayfinding-breadcrumbs_feature_div",
        ".a-breadcrumb",
        "#nav-subnav",
        "ul.a-unordered-list.a-horizontal a",
    ):
        el = page.locator(sel)
        cnt = await el.count()
        if cnt:
            text = (await el.first.inner_text()).strip()
            print(f"  '{sel}': '{text[:200]}'")

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
