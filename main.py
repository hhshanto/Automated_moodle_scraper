"""
main.py

Entry point for the Moodle Scraper. Supports four modes:

Usage:
    MCP server (for Claude Desktop / VS Code Copilot):
        python main.py

    MCP dev inspector (test tools in browser):
        mcp dev src/moodle_scraper/mcp_server.py

    Azure OpenAI agent (standalone, give it a goal):
        python main.py --agent

    Course navigator (log in and go to a specific course):
        python main.py --course

    Manual login test (no LLM, just browser):
        python main.py --test-login
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from moodle_scraper.utils import configure_logging

load_dotenv()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

configure_logging()
logger = logging.getLogger(__name__)


async def test_login():
    """Log into Moodle manually to verify credentials and browser setup."""
    from moodle_scraper import auth
    from moodle_scraper.browser import close_browser, launch_browser, clear_cookies_and_cache, take_screenshot
    from moodle_scraper.utils import build_timestamp_string, get_screenshot_directory

    moodle_url = os.getenv("MOODLE_BASE_URL", "").strip()
    username = os.getenv("MOODLE_USERNAME", "").strip()
    password = os.getenv("MOODLE_PASSWORD", "").strip()

    if not moodle_url or not username or not password:
        print("Set MOODLE_BASE_URL, MOODLE_USERNAME, and MOODLE_PASSWORD in your .env file.")
        return

    print("\nLaunching browser...")
    await launch_browser()
    await clear_cookies_and_cache()

    print(f"Logging into Moodle as '{username}' ...")
    is_login_successful = await auth.login_to_moodle(username, password, moodle_url)

    if not is_login_successful:
        print("Login FAILED. Check your credentials in .env.")
        await close_browser()
        return

    print("Login successful.")

    screenshot_path = get_screenshot_directory() / f"login_{build_timestamp_string()}.png"
    await take_screenshot(str(screenshot_path))
    print(f"Screenshot saved to: {screenshot_path}")

    input("\nPress Enter to close the browser...")
    await close_browser()
    print("Browser closed.")


async def run_agent_mode():
    """Ask the user for a goal and let the Azure OpenAI agent work on it."""
    from moodle_scraper.agent import run_agent

    print("\n========================================")
    print("  Moodle Scraper -- Agent Mode")
    print("========================================")
    print("The agent will use Azure OpenAI to decide which tools to call.")
    print("It can log in, navigate, read pages, and take screenshots.\n")

    goal = input("What do you want the agent to do?\nGoal: ").strip()
    if not goal:
        print("No goal entered.")
        return

    print(f"\nAgent starting. Goal: {goal}\n")

    summary = await run_agent(goal)

    print(f"\n========================================")
    print(f"Agent finished.")
    print(f"Summary: {summary}")
    print(f"========================================")


async def run_course_mode():
    """Run the course navigator agent to find and open a specific course."""
    from moodle_scraper.agent import run_course_agent

    print("\n========================================")
    print("  Moodle Scraper -- Course Navigator")
    print("========================================\n")

    course_name = input("Enter the course name to navigate to:\nCourse: ").strip()
    if not course_name:
        print("No course name entered.")
        return

    print(f"\nNavigating to course: {course_name}\n")

    summary = await run_course_agent(course_name)

    print(f"\n========================================")
    print(f"Course navigator finished.")
    print(f"Summary: {summary}")
    print(f"========================================")


def main():
    """Parse arguments and run the appropriate mode."""
    if "--test-login" in sys.argv:
        asyncio.run(test_login())
    elif "--course" in sys.argv:
        asyncio.run(run_course_mode())
    elif "--agent" in sys.argv:
        asyncio.run(run_agent_mode())
    else:
        from moodle_scraper.mcp_server import mcp
        mcp.run()


if __name__ == "__main__":
    main()

