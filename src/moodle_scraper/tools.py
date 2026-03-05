"""
tools.py

Single source of truth for all tool implementations. Both the MCP server
and the agent loop call these functions, so the logic is never duplicated.

Every tool function returns a plain dict -- either with the result or an
"error" key. Tools never raise exceptions.
"""

import asyncio
import json
import logging
import os

from moodle_scraper import auth
from moodle_scraper.browser import (
    active_session,
    clear_cookies_and_cache,
    close_browser as _close_browser,
    get_page_text,
    launch_browser,
    navigate_to_url,
    take_screenshot as _take_screenshot,
)
from moodle_scraper.utils import build_timestamp_string, get_screenshot_directory

logger = logging.getLogger(__name__)


async def login() -> dict:
    """
    Launch a browser, clear cookies, and log into Moodle.

    Reads MOODLE_BASE_URL, MOODLE_USERNAME, and MOODLE_PASSWORD from the
    environment.

    Returns:
        A dict with "status": "logged_in" and the page title on success,
        or "error" describing what went wrong.
    """
    moodle_url = os.getenv("MOODLE_BASE_URL", "").strip()
    username = os.getenv("MOODLE_USERNAME", "").strip()
    password = os.getenv("MOODLE_PASSWORD", "").strip()

    if not moodle_url or not username or not password:
        return {"error": "MOODLE_BASE_URL, MOODLE_USERNAME, or MOODLE_PASSWORD is not set in .env"}

    try:
        await launch_browser()
        await clear_cookies_and_cache()

        is_login_successful = await auth.login_to_moodle(username, password, moodle_url)
        if not is_login_successful:
            return {"error": "Login failed. Moodle rejected the credentials."}

        page_title = await active_session.page.title()
        return {"status": "logged_in", "page_title": page_title}

    except Exception as error:
        logger.error("login tool failed: %s", error)
        return {"error": str(error)}


async def navigate(url: str) -> dict:
    """
    Navigate the browser to a specific URL.

    Args:
        url: The full URL to navigate to.

    Returns:
        A dict with "status", "url", and "page_title" on success,
        or "error" on failure.
    """
    try:
        page_title = await navigate_to_url(url)
        return {"status": "navigated", "url": url, "page_title": page_title}
    except Exception as error:
        logger.error("navigate tool failed: %s", error)
        return {"error": str(error)}


async def take_screenshot(label: str = "screenshot") -> dict:
    """
    Take a screenshot of the current browser page and save it to output/screenshots/.

    Args:
        label: A short label included in the filename to identify the screenshot.

    Returns:
        A dict with "file_path" of the saved PNG, or "error" on failure.
    """
    try:
        timestamp = build_timestamp_string()
        screenshot_dir = get_screenshot_directory()
        file_path = screenshot_dir / f"{label}_{timestamp}.png"
        await _take_screenshot(str(file_path))
        return {"file_path": str(file_path)}
    except Exception as error:
        logger.error("take_screenshot tool failed: %s", error)
        return {"error": str(error)}


async def get_page_content() -> dict:
    """
    Return the text content of the current browser page.

    Returns:
        A dict with "page_text" on success, or "error" on failure.
    """
    try:
        if active_session.page is None:
            return {"error": "Browser is not running."}

        text_content = await get_page_text()
        return {"page_text": text_content}
    except Exception as error:
        logger.error("get_page_content tool failed: %s", error)
        return {"error": str(error)}


async def get_status() -> dict:
    """
    Check if the browser is open, if logged in, and what URL is loaded.

    Returns:
        A dict with "is_browser_open", "is_logged_in", and "current_url".
    """
    is_browser_open = active_session.page is not None
    current_url = ""

    if is_browser_open:
        try:
            current_url = active_session.page.url
        except Exception:
            current_url = "unknown"

    return {
        "is_browser_open": is_browser_open,
        "is_logged_in": active_session.is_logged_in,
        "current_url": current_url,
    }


async def wait_on_page(seconds: int = 5) -> dict:
    """
    Wait on the current browser page for a given number of seconds without navigating away.

    Use this when you need the browser to stay open and idle on a page --
    for example, after login, to keep the session alive on the home page.

    Args:
        seconds: How many seconds to wait. Defaults to 5.

    Returns:
        A dict with "status": "waited", the current URL, and how long it waited,
        or "error" if the browser is not running.
    """
    if active_session.page is None:
        return {"error": "Browser is not running."}

    try:
        current_url = active_session.page.url
        await asyncio.sleep(seconds)
        return {"status": "waited", "url": current_url, "seconds": seconds}
    except Exception as error:
        logger.error("wait_on_page tool failed: %s", error)
        return {"error": str(error)}


async def close_browser() -> dict:
    """
    Close the browser and end the session.

    Returns:
        A dict with "status": "browser_closed", or "error" on failure.
    """
    try:
        await _close_browser()
        return {"status": "browser_closed"}
    except Exception as error:
        logger.error("close_browser tool failed: %s", error)
        return {"error": str(error)}


# ---------------------------------------------------------------------------
# Tool registry -- maps tool name to (function, openai_schema) pairs.
# Used by the agent to auto-build TOOL_DEFINITIONS and dispatch calls.
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "login": {
        "function": login,
        "schema": {
            "type": "function",
            "function": {
                "name": "login",
                "description": (
                    "Launch a browser, clear cookies, and log into Moodle. "
                    "Credentials are read from environment variables automatically."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },
    "navigate": {
        "function": navigate,
        "schema": {
            "type": "function",
            "function": {
                "name": "navigate",
                "description": "Navigate the browser to a specific URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The full URL to navigate to."},
                    },
                    "required": ["url"],
                },
            },
        },
    },
    "take_screenshot": {
        "function": take_screenshot,
        "schema": {
            "type": "function",
            "function": {
                "name": "take_screenshot",
                "description": "Take a screenshot of the current browser page.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "A short label for the screenshot filename.",
                        },
                    },
                    "required": [],
                },
            },
        },
    },
    "get_page_content": {
        "function": get_page_content,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_page_content",
                "description": (
                    "Return the text content of the current browser page. "
                    "Use this to read what is on screen."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },
    "get_status": {
        "function": get_status,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_status",
                "description": "Check if the browser is open, if logged in, and what URL is loaded.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },
    "wait_on_page": {
        "function": wait_on_page,
        "schema": {
            "type": "function",
            "function": {
                "name": "wait_on_page",
                "description": (
                    "Wait on the current browser page for a given number of seconds "
                    "without navigating away. Use this to keep the session open and idle."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "seconds": {
                            "type": "integer",
                            "description": "How many seconds to wait. Defaults to 5.",
                        },
                    },
                    "required": [],
                },
            },
        },
    },
    "close_browser": {
        "function": close_browser,
        "schema": {
            "type": "function",
            "function": {
                "name": "close_browser",
                "description": "Close the browser and end the session.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },
}


def get_tool_definitions(tool_names: list[str] | None = None) -> list[dict]:
    """
    Build the OpenAI tool definitions list from the registry.

    Args:
        tool_names: Optional list of tool names to include. If None, all tools
                    are included.

    Returns:
        A list of OpenAI-format tool definition dicts.
    """
    if tool_names is None:
        tool_names = list(TOOL_REGISTRY.keys())

    return [TOOL_REGISTRY[name]["schema"] for name in tool_names if name in TOOL_REGISTRY]


async def execute_tool(tool_name: str, tool_arguments: dict) -> str:
    """
    Look up a tool by name in the registry and execute it.

    Args:
        tool_name:      The name of the tool to execute.
        tool_arguments: The arguments dict parsed from the model's response.

    Returns:
        A JSON string containing the tool result.
    """
    logger.info("Executing tool: %s with args: %s", tool_name, tool_arguments)

    if tool_name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    tool_function = TOOL_REGISTRY[tool_name]["function"]
    result = await tool_function(**tool_arguments)
    return json.dumps(result)
