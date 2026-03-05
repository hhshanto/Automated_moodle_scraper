"""
mcp_server.py

The MCP server that exposes scraping capabilities as tools to external LLM
clients. Each @mcp.tool() is a thin wrapper around the shared implementation
in tools.py, so logic is never duplicated between the MCP server and the agent.

Tools never raise exceptions -- they always return a plain dict with either
the result or an "error" key.
"""

import logging

from mcp.server.fastmcp import FastMCP

from moodle_scraper import tools
from moodle_scraper.utils import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

mcp = FastMCP("moodle-scraper")


@mcp.tool()
async def login() -> dict:
    """
    Launch a browser, clear cookies, and log into Moodle.

    Reads MOODLE_BASE_URL, MOODLE_USERNAME, and MOODLE_PASSWORD from the
    environment. Set HEADLESS=false in .env to watch the browser on screen.

    Returns:
        A dict with "status": "logged_in" and the page title on success,
        or "error" describing what went wrong.
    """
    return await tools.login()


@mcp.tool()
async def navigate(url: str) -> dict:
    """
    Navigate the browser to a specific URL.

    Args:
        url: The full URL to navigate to.

    Returns:
        A dict with "status", "url", and "page_title" on success,
        or "error" on failure.
    """
    return await tools.navigate(url)


@mcp.tool()
async def take_screenshot(label: str = "screenshot") -> dict:
    """
    Take a screenshot of the current browser page and save it to output/screenshots/.

    Args:
        label: A short label included in the filename to identify the screenshot.

    Returns:
        A dict with "file_path" of the saved PNG, or "error" on failure.
    """
    return await tools.take_screenshot(label)


@mcp.tool()
async def get_page_content() -> dict:
    """
    Return the text content of the current browser page.

    Returns:
        A dict with "page_text" on success, or "error" on failure.
    """
    return await tools.get_page_content()


@mcp.tool()
async def get_status() -> dict:
    """
    Return the current session status: whether the browser is open, whether
    the user is logged in, and what URL is currently loaded.

    Returns:
        A dict with "is_browser_open", "is_logged_in", and "current_url".
    """
    return await tools.get_status()


@mcp.tool()
async def wait_on_page(seconds: int = 5) -> dict:
    """
    Wait on the current browser page for a given number of seconds without navigating away.

    Args:
        seconds: How many seconds to wait. Defaults to 5.

    Returns:
        A dict with "status": "waited", the current URL, and how long it waited,
        or "error" if the browser is not running.
    """
    return await tools.wait_on_page(seconds)


@mcp.tool()
async def close_browser() -> dict:
    """
    Close the browser and end the session.

    Returns:
        A dict with "status": "browser_closed", or "error" on failure.
    """
    return await tools.close_browser()


if __name__ == "__main__":
    mcp.run()

