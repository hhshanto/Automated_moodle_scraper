"""
browser.py

Manages the Playwright browser lifecycle: launching, navigating, screenshots,
cookie management, and shutdown. All other modules that need a browser import
the shared active_session from here.

This module has no knowledge of Moodle, authentication, or scraping logic.
"""

import logging
import os

from dotenv import load_dotenv
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

load_dotenv()

logger = logging.getLogger(__name__)

IS_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class BrowserSession:
    """
    Holds the active Playwright browser objects for the duration of the session.
    Only one session is active at a time (module-level singleton below).
    """

    def __init__(self) -> None:
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.is_logged_in: bool = False
        self._playwright = None


# The single shared session used by all other modules.
active_session = BrowserSession()


async def launch_browser() -> None:
    """
    Start a Chromium browser and open a blank page.

    If a browser is already running, this function does nothing, so it is safe
    to call multiple times across separate agent runs without opening new windows.

    Reads HEADLESS from the environment. Set HEADLESS=false in .env to watch
    the browser window on screen.

    Returns:
        None. Stores the browser, context, and page on active_session.
    """
    if active_session.page is not None:
        logger.info("Browser already running -- reusing existing session.")
        return

    active_session._playwright = await async_playwright().start()
    active_session.browser = await active_session._playwright.chromium.launch(headless=IS_HEADLESS)
    active_session.context = await active_session.browser.new_context()
    active_session.page = await active_session.context.new_page()
    logger.info("Browser launched. Headless: %s", IS_HEADLESS)


async def navigate_to_url(url: str) -> str:
    """
    Navigate the active browser page to the given URL and return the page title.

    Args:
        url: The full URL to navigate to.

    Returns:
        The page title as a string after navigation completes.
    """
    if active_session.page is None:
        raise RuntimeError("Browser is not running. Call launch_browser() first.")

    await active_session.page.goto(url, wait_until="domcontentloaded")
    await active_session.page.wait_for_load_state("networkidle")
    page_title = await active_session.page.title()
    logger.info("Navigated to %s -- title: %s", url, page_title)
    return page_title


async def take_screenshot(file_path: str) -> None:
    """
    Save a screenshot of the current browser page to disk.

    Args:
        file_path: The full path where the screenshot PNG will be saved.

    Returns:
        None.
    """
    if active_session.page is None:
        raise RuntimeError("Browser is not running. Call launch_browser() first.")

    await active_session.page.screenshot(path=file_path, full_page=True)
    logger.info("Screenshot saved to %s", file_path)


async def get_page_text() -> str:
    """
    Return the visible text content of the current browser page.

    Long pages are truncated to 4000 characters to keep LLM token usage reasonable.

    Returns:
        The visible text of the page body.
    """
    if active_session.page is None:
        raise RuntimeError("Browser is not running. Call launch_browser() first.")

    text_content = await active_session.page.inner_text("body")

    max_characters = 4000
    if len(text_content) > max_characters:
        text_content = text_content[:max_characters] + "\n... (truncated)"

    return text_content


async def clear_cookies_and_cache() -> None:
    """
    Clear all cookies and browser storage from the active browser context.

    Returns:
        None.
    """
    if active_session.context is None:
        raise RuntimeError("Browser is not running. Call launch_browser() first.")

    await active_session.context.clear_cookies()
    logger.info("Browser cookies cleared.")

    if active_session.page is not None:
        try:
            await active_session.page.evaluate("localStorage.clear()")
            await active_session.page.evaluate("sessionStorage.clear()")
            logger.info("Browser localStorage and sessionStorage cleared.")
        except Exception:
            pass


async def close_browser() -> None:
    """
    Close the browser and reset the active session.

    Returns:
        None.
    """
    if active_session.browser is not None:
        await active_session.browser.close()
    if active_session._playwright is not None:
        await active_session._playwright.stop()

    active_session.browser = None
    active_session.context = None
    active_session.page = None
    active_session.is_logged_in = False
    active_session._playwright = None
    logger.info("Browser closed.")
