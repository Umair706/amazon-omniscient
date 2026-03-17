"""Automated login to 1688.com using Playwright."""

import asyncio
import logging

from playwright.async_api import async_playwright

from app.core.cookie_manager import CookieManager

logger = logging.getLogger(__name__)


class AlibabaLoginService:
    """Log in to 1688.com and persist session cookies via CookieManager."""

    def __init__(self, cookie_manager: CookieManager):
        self.cookies = cookie_manager

    async def ensure_logged_in(self, email: str, password: str) -> str | None:
        """Ensure we have valid 1688 cookies. Log in if needed.

        Returns
        -------
        str | None
            Path to storage_state file, or ``None`` if login failed.
        """
        if self.cookies.has_valid_cookies("1688"):
            logger.debug("Using cached 1688 cookies")
            return self.cookies.get_storage_state("1688")

        return await self._perform_login(email, password)

    async def _perform_login(self, email: str, password: str) -> str | None:
        """Log in to 1688 and save cookies."""
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
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
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
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                """
            )

            # Navigate to login page
            await page.goto(
                "https://login.1688.com/member/signin.htm",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            await asyncio.sleep(2)

            # Switch to password login tab
            for tab_sel in (
                'div[data-widget-cid*="loginByPassword"]',
                'a:has-text("密码登录")',
                'div.login-tab:has-text("密码登录")',
            ):
                try:
                    tab = page.locator(tab_sel).first
                    if await tab.count():
                        await tab.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

            # Fill credentials
            for id_sel in ('#fm-login-id', 'input[name="loginId"]'):
                try:
                    el = page.locator(id_sel).first
                    if await el.count():
                        await el.fill(email)
                        break
                except Exception:
                    continue

            for pw_sel in ('#fm-login-password', 'input[name="password"]'):
                try:
                    el = page.locator(pw_sel).first
                    if await el.count():
                        await el.fill(password)
                        break
                except Exception:
                    continue

            await asyncio.sleep(0.5)

            # Submit
            for btn_sel in ('#fm-login-submit', 'button[type="submit"]'):
                try:
                    el = page.locator(btn_sel).first
                    if await el.count():
                        await el.click()
                        break
                except Exception:
                    continue

            # Wait for redirect (login success takes us to 1688 homepage)
            try:
                await page.wait_for_url("**/1688.com/**", timeout=30_000)
                logger.info("1688 login succeeded")
            except Exception:
                logger.warning(
                    "1688 login may require manual verification (CAPTCHA/SMS). "
                    "Saving cookies anyway in case partial session helps."
                )

            # Save cookies regardless — partial sessions can still help
            await self.cookies.save_storage_state(context, "1688")
            return self.cookies.get_storage_state("1688")

        except Exception as e:
            logger.error("1688 login failed: %s", e)
            return None
        finally:
            if browser:
                await browser.close()
            try:
                await pw.stop()
            except Exception:
                pass
