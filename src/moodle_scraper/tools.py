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
from moodle_scraper.utils import build_timestamp_string, get_screenshot_directory, get_downloads_directory

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


async def extract_links() -> dict:
    """
    Extract all links from the current browser page.

    Returns a list of dicts, each with "text" (the visible link text) and
    "url" (the href). Useful for discovering course links, quiz links, etc.

    Returns:
        A dict with "links": [{"text": ..., "url": ...}, ...] on success,
        or "error" on failure.
    """
    if active_session.page is None:
        return {"error": "Browser is not running."}

    try:
        links = await active_session.page.evaluate(
            """() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({ text: a.innerText.trim(), url: a.href }))
                    .filter(link => link.text.length > 0 && link.url.startsWith('http'));
            }"""
        )
        return {"links": links, "count": len(links)}
    except Exception as error:
        logger.error("extract_links tool failed: %s", error)
        return {"error": str(error)}


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


async def get_select_options(selector: str) -> dict:
    """
    Return all options from a <select> dropdown element.

    ALWAYS call this before using fill_form_field on a <select>, so you can
    identify the correct value attribute for each option. This is especially
    important when multiple options share the same visible label (e.g. "Quizz"
    appearing under several weeks) -- the value attribute is the only way to
    distinguish them.

    Args:
        selector: A CSS selector identifying the <select> element.

    Returns:
        A dict with "options": [{"value": ..., "label": ..., "is_selected": ...}]
        and "count", or "error" on failure.
    """
    if active_session.page is None:
        return {"error": "Browser is not running."}

    try:
        options = await active_session.page.evaluate(
            """(selector) => {
                const select = document.querySelector(selector);
                if (!select) return null;
                return Array.from(select.options).map(o => ({
                    value: o.value,
                    label: o.text.trim(),
                    is_selected: o.selected
                }));
            }""",
            selector,
        )
        if options is None:
            return {"error": f"No <select> element found for selector: {selector}"}
        return {"options": options, "count": len(options)}
    except Exception as error:
        logger.error("get_select_options tool failed for selector '%s': %s", selector, error)
        return {"error": str(error)}


async def click_and_download(selector: str, label: str = "download") -> dict:
    """
    Click an element that triggers a file download and save the file to output/downloads/.

    Use this instead of click_element when the button or link causes a file to
    be downloaded (e.g. "Export questions to file" on the Moodle export page).
    The downloaded file is saved with a timestamp in the filename.

    Args:
        selector: A CSS selector identifying the button or link to click.
        label:    A short label included in the saved filename. Defaults to "download".

    Returns:
        A dict with "file_path" of the saved file and "original_filename",
        or "error" on failure.
    """
    if active_session.page is None:
        return {"error": "Browser is not running."}

    try:
        downloads_dir = get_downloads_directory()
        timestamp = build_timestamp_string()

        async with active_session.page.expect_download() as download_info:
            await active_session.page.click(selector)

        download = await download_info.value
        original_filename = download.suggested_filename
        save_path = downloads_dir / f"{label}_{timestamp}_{original_filename}"
        await download.save_as(str(save_path))

        logger.info("Downloaded file saved to: %s", save_path)
        return {"file_path": str(save_path), "original_filename": original_filename}
    except Exception as error:
        logger.error("click_and_download tool failed for selector '%s': %s", selector, error)
        return {"error": str(error)}


async def click_element(selector: str) -> dict:
    """
    Click an element on the current page identified by a CSS selector.

    Use this to click buttons, radio buttons, checkboxes, links, or any other
    clickable element. For radio buttons use selectors like
    'input[type="radio"][value="moodle_xml"]' or locate by label text.

    Args:
        selector: A CSS selector that uniquely identifies the element to click.

    Returns:
        A dict with "status": "clicked" and the selector used, or "error" on failure.
    """
    if active_session.page is None:
        return {"error": "Browser is not running."}

    try:
        await active_session.page.click(selector)
        await active_session.page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)
        return {"status": "clicked", "selector": selector}
    except Exception as error:
        logger.error("click_element tool failed for selector '%s': %s", selector, error)
        return {"error": str(error)}


async def fill_form_field(selector: str, value: str) -> dict:
    """
    Fill a form field on the current page with a value.

    Works for text inputs, textareas, and <select> dropdowns.
    For a <select>, pass the option's VALUE attribute (not the visible label
    text). Call get_select_options() first to inspect available values before
    selecting -- this avoids ambiguity when multiple options share the same
    visible label. Falls back to label matching only if the value does not match.

    Args:
        selector: A CSS selector that uniquely identifies the form field.
        value:    The value to fill in. For <select> elements, pass the option's
                  value attribute (e.g. "6641,229221"), not the visible label.

    Returns:
        A dict with "status": "filled", the selector, and the value used,
        or "error" on failure.
    """
    if active_session.page is None:
        return {"error": "Browser is not running."}

    try:
        tag_name = await active_session.page.eval_on_selector(selector, "el => el.tagName.toLowerCase()")
        if tag_name == "select":
            try:
                await active_session.page.select_option(selector, value=value)
            except Exception:
                # Fall back to label matching if value attribute does not match.
                await active_session.page.select_option(selector, label=value)
        else:
            await active_session.page.fill(selector, value)
        return {"status": "filled", "selector": selector, "value": value}
    except Exception as error:
        logger.error("fill_form_field tool failed for selector '%s': %s", selector, error)
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
    "extract_links": {
        "function": extract_links,
        "schema": {
            "type": "function",
            "function": {
                "name": "extract_links",
                "description": (
                    "Extract all links from the current browser page. "
                    "Returns a list of link text and URLs. Use this to find "
                    "course links, quiz links, or any other clickable links."
                ),
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
    "click_element": {
        "function": click_element,
        "schema": {
            "type": "function",
            "function": {
                "name": "click_element",
                "description": (
                    "Click an element on the current page using a CSS selector. "
                    "Use this for radio buttons, checkboxes, navigation links, and form submissions "
                    "that do NOT trigger a file download. "
                    "WARNING: Do NOT use this for buttons that cause a file to be downloaded "
                    "(e.g. 'Export questions to file'). Use click_and_download instead."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "A CSS selector identifying the element to click.",
                        },
                    },
                    "required": ["selector"],
                },
            },
        },
    },
    "click_and_download": {
        "function": click_and_download,
        "schema": {
            "type": "function",
            "function": {
                "name": "click_and_download",
                "description": (
                    "Click a button or link that triggers a file download and save the file "
                    "to output/downloads/. Use this instead of click_element when the action "
                    "causes a file download (e.g. the 'Export questions to file' button)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "A CSS selector identifying the button or link to click.",
                        },
                        "label": {
                            "type": "string",
                            "description": "A short label for the saved filename. Defaults to 'download'.",
                        },
                    },
                    "required": ["selector"],
                },
            },
        },
    },
    "get_select_options": {
        "function": get_select_options,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_select_options",
                "description": (
                    "Return all options from a <select> dropdown on the current page. "
                    "ALWAYS call this before fill_form_field on a <select> to get the "
                    "exact value attribute for each option. Multiple options can share "
                    "the same visible label (e.g. 'Quizz') -- the value attribute is the "
                    "only way to distinguish them."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "A CSS selector identifying the <select> element.",
                        },
                    },
                    "required": ["selector"],
                },
            },
        },
    },
    "fill_form_field": {
        "function": fill_form_field,
        "schema": {
            "type": "function",
            "function": {
                "name": "fill_form_field",
                "description": (
                    "Fill a form field with a value. For <select> dropdowns, pass the "
                    "option's VALUE attribute (not the visible label text). Always call "
                    "get_select_options first to find the correct value. Falls back to "
                    "label matching if the value does not match."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "A CSS selector identifying the form field.",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value to fill in, or option text for selects.",
                        },
                    },
                    "required": ["selector", "value"],
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
