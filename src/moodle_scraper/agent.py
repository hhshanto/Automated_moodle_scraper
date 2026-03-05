"""
agent.py

The Azure OpenAI agent loop. Takes a plain-English goal, sends it to Azure
OpenAI with tool definitions, executes whichever tool the model picks,
feeds the result back, and repeats until the model says it is done.

The available tools match what the MCP server exposes, but are called
directly via auth.py so this agent can run standalone without an MCP client.
"""

import asyncio
import json
import logging
import os

from moodle_scraper import auth, parser
from moodle_scraper.utils import build_timestamp_string, get_screenshot_directory

logger = logging.getLogger(__name__)

MAX_STEPS = 20

# ---------------------------------------------------------------------------
# Tool definitions sent to Azure OpenAI so the model knows what it can call.
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Check if the browser is open, if logged in, and what URL is loaded.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_browser",
            "description": "Close the browser and end the session.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Call this when the goal has been fully accomplished. Include a summary of what was done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "A summary of what was accomplished."},
                },
                "required": ["summary"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool execution -- each function matches a name in TOOL_DEFINITIONS.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a browser automation agent for Moodle. "
    "You have tools to control a browser. Use them step by step to accomplish the user's goal. "
    "After each tool call you will see its result. Decide the next tool to call based on that result. "
    "When the goal is fully accomplished, call the 'done' tool with a summary. "
    "If you get stuck, call 'done' and explain what went wrong in the summary."
)


async def execute_tool_call(tool_name: str, tool_arguments: dict) -> str:
    """
    Execute a single tool call and return the result as a JSON string.

    Args:
        tool_name:      The name of the tool to execute.
        tool_arguments: The arguments dict parsed from the model's response.

    Returns:
        A JSON string containing the tool result.
    """
    logger.info("Executing tool: %s with args: %s", tool_name, tool_arguments)

    if tool_name == "login":
        return await _execute_login()

    if tool_name == "navigate":
        return await _execute_navigate(tool_arguments.get("url", ""))

    if tool_name == "take_screenshot":
        return await _execute_take_screenshot(tool_arguments.get("label", "agent"))

    if tool_name == "get_page_content":
        return await _execute_get_page_content()

    if tool_name == "get_status":
        return await _execute_get_status()

    if tool_name == "close_browser":
        return await _execute_close_browser()

    if tool_name == "done":
        return json.dumps({"status": "done", "summary": tool_arguments.get("summary", "")})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def _execute_login() -> str:
    """Launch browser and log into Moodle using .env credentials."""
    moodle_url = os.getenv("MOODLE_BASE_URL", "").strip()
    username = os.getenv("MOODLE_USERNAME", "").strip()
    password = os.getenv("MOODLE_PASSWORD", "").strip()

    if not moodle_url or not username or not password:
        return json.dumps({"error": "Missing MOODLE_BASE_URL, MOODLE_USERNAME, or MOODLE_PASSWORD in .env"})

    try:
        await auth.launch_browser()
        await auth.clear_cookies_and_cache()
        is_login_successful = await auth.login_to_moodle(username, password, moodle_url)

        if not is_login_successful:
            return json.dumps({"error": "Login failed. Moodle rejected the credentials."})

        page_title = await auth.active_session.page.title()
        return json.dumps({"status": "logged_in", "page_title": page_title})

    except Exception as error:
        logger.error("login tool failed: %s", error)
        return json.dumps({"error": str(error)})


async def _execute_navigate(url: str) -> str:
    """Navigate the browser to a URL."""
    try:
        page_title = await auth.navigate_to_url(url)
        return json.dumps({"status": "navigated", "url": url, "page_title": page_title})
    except Exception as error:
        logger.error("navigate tool failed: %s", error)
        return json.dumps({"error": str(error)})


async def _execute_take_screenshot(label: str) -> str:
    """Take a screenshot and return the file path."""
    try:
        timestamp = build_timestamp_string()
        screenshot_dir = get_screenshot_directory()
        file_path = screenshot_dir / f"{label}_{timestamp}.png"
        await auth.take_screenshot(str(file_path))
        return json.dumps({"file_path": str(file_path)})
    except Exception as error:
        logger.error("take_screenshot tool failed: %s", error)
        return json.dumps({"error": str(error)})


async def _execute_get_page_content() -> str:
    """Return the visible text content of the current page."""
    try:
        if auth.active_session.page is None:
            return json.dumps({"error": "Browser is not running."})

        # Get visible text only, not full HTML, to keep token usage reasonable.
        text_content = await auth.active_session.page.inner_text("body")

        # Truncate to avoid blowing up the context window.
        max_characters = 4000
        if len(text_content) > max_characters:
            text_content = text_content[:max_characters] + "\n... (truncated)"

        return json.dumps({"page_text": text_content})
    except Exception as error:
        logger.error("get_page_content tool failed: %s", error)
        return json.dumps({"error": str(error)})


async def _execute_get_status() -> str:
    """Return browser and login status."""
    is_browser_open = auth.active_session.page is not None
    current_url = ""

    if is_browser_open:
        try:
            current_url = auth.active_session.page.url
        except Exception:
            current_url = "unknown"

    return json.dumps({
        "is_browser_open": is_browser_open,
        "is_logged_in": auth.active_session.is_logged_in,
        "current_url": current_url,
    })


async def _execute_close_browser() -> str:
    """Close the browser session."""
    try:
        await auth.close_browser()
        return json.dumps({"status": "browser_closed"})
    except Exception as error:
        logger.error("close_browser tool failed: %s", error)
        return json.dumps({"error": str(error)})


# ---------------------------------------------------------------------------
# The main agent loop.
# ---------------------------------------------------------------------------

async def run_agent(goal: str) -> str:
    """
    Run the agent loop: send the goal to Azure OpenAI, execute tool calls,
    feed results back, repeat until the model calls 'done' or MAX_STEPS.

    Args:
        goal: Plain-English description of what to accomplish.

    Returns:
        A summary string of what the agent accomplished.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]

    for step_number in range(1, MAX_STEPS + 1):
        logger.info("Agent step %d", step_number)

        response = parser.call_azure_openai(messages, tools=TOOL_DEFINITIONS)
        response_message = response.choices[0].message

        # If the model wants to call tools, execute them.
        if response_message.tool_calls:
            # Add the assistant message with tool_calls to the conversation.
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_arguments = json.loads(tool_call.function.arguments)

                print(f"  Step {step_number}: calling {tool_name}({tool_arguments})")

                # Check for "done" before executing.
                if tool_name == "done":
                    summary = tool_arguments.get("summary", "No summary provided.")
                    logger.info("Agent finished: %s", summary)
                    return summary

                tool_result = await execute_tool_call(tool_name, tool_arguments)
                logger.info("Tool result: %s", tool_result)

                # Feed the tool result back to the model.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

            continue

        # If the model responds with plain text (no tool call), we are done.
        final_text = response_message.content or "Agent finished without a summary."
        logger.info("Agent responded with text: %s", final_text)
        return final_text

    return "Agent reached the maximum number of steps without completing the goal."

