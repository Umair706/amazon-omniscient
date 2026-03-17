"""Automated login to Amazon using Playwright."""

import asyncio
import logging

from playwright.async_api import async_playwright

from app.core.cookie_manager import CookieManager

logger = logging.getLogger(__name__)


class AmazonLoginService:
    """Log in to Amazon and persist session cookies via CookieManager.

    This is an optional fallback — product-page review extraction does not
    require login.  Having Amazon cookies enables access to the dedicated
    ``/product-reviews/`` pages if more reviews are needed.
    """

    def __init__(self, cookie_manager: CookieManager):
        self.cookies = cookie_manager

    async def ensure_logged_in(self, email: str, password: str) -> str | None:
        """Ensure we have valid Amazon cookies. Log in if needed.

        Returns
        -------
        str | None
            Path to storage_state file, or ``None`` if login failed.
        """
        if self.cookies.has_valid_cookies("amazon"):
            logger.debug("Using cached Amazon cookies")
            return self.cookies.get_storage_state("amazon")

        return await self._perform_login(email, password)

    async def _perform_login(self, email: str, password: str) -> str | None:
        """Log in to Amazon and save cookies."""
        pw = await async_playwright().start()
        browser = None
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                locale="en-US",
                timezone_id="America/New_York",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            # Mask webdriver property
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                """
            )

            # Navigate to sign-in page
            await page.goto(
                "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0"
                "&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F"
                "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
                "&openid.assoc_handle=usflex"
                "&openid.mode=checkid_setup"
                "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
                "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            await asyncio.sleep(2)

            # Fill email
            try:
                email_el = page.locator('#ap_email, input[name="email"]').first
                if await email_el.count():
                    await email_el.fill(email)
            except Exception:
                pass

            # Click continue (Amazon splits email and password into two steps)
            try:
                continue_btn = page.locator('#continue, input#continue').first
                if await continue_btn.count():
                    await continue_btn.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

            # Fill password
            try:
                pw_el = page.locator('#ap_password, input[name="password"]').first
                if await pw_el.count():
                    await pw_el.fill(password)
            except Exception:
                pass

            await asyncio.sleep(0.5)

            # Submit
            try:
                submit_btn = page.locator('#signInSubmit, input[name="signIn"]').first
                if await submit_btn.count():
                    await submit_btn.click()
            except Exception:
                pass

            # Wait for redirect to Amazon homepage
            try:
                await page.wait_for_url("**/amazon.com/**", timeout=30_000)
                logger.info("Amazon login succeeded")
            except Exception:
                logger.warning(
                    "Amazon login may require CAPTCHA or 2FA verification. "
                    "Saving cookies anyway."
                )

            # Save cookies
            await self.cookies.save_storage_state(context, "amazon")
            return self.cookies.get_storage_state("amazon")

        except Exception as e:
            logger.error("Amazon login failed: %s", e)
            return None
        finally:
            if browser:
                await browser.close()
            try:
                await pw.stop()
            except Exception:
                pass
