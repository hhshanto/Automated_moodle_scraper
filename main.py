"""
main.py

Entry point for the Moodle Scraper. Supports six modes:

Usage:
    MCP server (for Claude Desktop / VS Code Copilot):
        python main.py

    MCP dev inspector (test tools in browser):
        mcp dev src/moodle_scraper/mcp_server.py

    Azure OpenAI agent (standalone, give it a goal):
        python main.py --agent

    Azure OpenAI agent (interactive -- keep giving it instructions):
        python main.py --chat

    Azure OpenAI agent (read goal from a text file):
        python main.py --prompt-file path/to/prompt.txt

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
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from moodle_scraper.utils import configure_logging

console = Console()

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
        console.print("[red]Set MOODLE_BASE_URL, MOODLE_USERNAME, and MOODLE_PASSWORD in your .env file.[/]")
        return

    console.print("\n[cyan]Launching browser...[/]")
    await launch_browser()
    await clear_cookies_and_cache()

    console.print(f"[cyan]Logging into Moodle as '[bold]{username}[/]' ...[/]")
    is_login_successful = await auth.login_to_moodle(username, password, moodle_url)

    if not is_login_successful:
        console.print("[bold red]Login FAILED.[/] Check your credentials in .env.")
        await close_browser()
        return

    console.print("[bold green]Login successful.[/]")

    screenshot_path = get_screenshot_directory() / f"login_{build_timestamp_string()}.png"
    await take_screenshot(str(screenshot_path))
    console.print(f"Screenshot saved to: [dim]{screenshot_path}[/]")

    input("\nPress Enter to close the browser...")
    await close_browser()
    console.print("[dim]Browser closed.[/]")


def _print_token_summary(summary: str | None, usage: dict) -> None:
    """Print a Rich table showing the agent summary and token usage."""
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Metric", style="dim", width=20)
    table.add_column("Value", justify="right")

    if summary:
        table.add_row("Summary", summary)

    table.add_row("Prompt tokens", str(usage["prompt_tokens"]))
    table.add_row("Completion tokens", str(usage["completion_tokens"]))
    table.add_row("Total tokens", f"[bold]{usage['total_tokens']}[/]")

    console.print(Panel(table, title="[bold green]Session Complete[/]", border_style="green"))


async def run_agent_mode():
    """Ask the user for a goal and let the Azure OpenAI agent work on it."""
    from moodle_scraper.agent import run_agent
    from moodle_scraper.browser import close_browser

    console.print(Panel(
        "The agent will use Azure OpenAI to decide which tools to call.\n"
        "It can log in, navigate, read pages, and take screenshots.",
        title="[bold cyan]Moodle Scraper -- Agent Mode[/]",
        border_style="cyan",
    ))

    goal = input("What do you want the agent to do?\nGoal: ").strip()
    if not goal:
        console.print("[yellow]No goal entered.[/]")
        return

    console.print(f"\n[bold]Agent starting.[/] Goal: [italic]{goal}[/]\n")

    try:
        summary = await run_agent(goal)
    finally:
        await close_browser()

    from moodle_scraper import parser
    _print_token_summary(summary, parser.TOKEN_USAGE)


async def run_prompt_file_mode(file_path: str):
    """Read a goal from a text file and run the agent with it."""
    from moodle_scraper.agent import run_agent
    from moodle_scraper.browser import close_browser
    from pathlib import Path

    prompt_path = Path(file_path)
    if not prompt_path.exists():
        console.print(f"[red]File not found:[/] {file_path}")
        return

    goal = prompt_path.read_text(encoding="utf-8").strip()
    if not goal:
        console.print(f"[yellow]File is empty:[/] {file_path}")
        return

    console.print(Panel(
        f"[dim]File:[/] {file_path}\n\n[italic]{goal}[/]",
        title="[bold cyan]Moodle Scraper -- Prompt File Mode[/]",
        border_style="cyan",
    ))

    try:
        summary = await run_agent(goal)
    finally:
        await close_browser()

    from moodle_scraper import parser
    _print_token_summary(summary, parser.TOKEN_USAGE)


async def run_chat_mode():
    """
    Interactive agent loop: the browser stays open between prompts.

    The user types one instruction at a time. The agent executes it,
    reports back, and waits for the next instruction. Type 'exit' to quit.
    """
    from moodle_scraper.agent import create_moodle_browser_agent
    from moodle_scraper.browser import close_browser

    console.print(Panel(
        "The browser stays open between instructions.\n"
        "Type your next instruction after each response.\n"
        "Type [bold]exit[/] or leave blank to quit and close the browser.",
        title="[bold cyan]Moodle Scraper -- Chat Mode[/]",
        border_style="cyan",
    ))

    agent = create_moodle_browser_agent()

    while True:
        instruction = input("You: ").strip()

        if not instruction or instruction.lower() == "exit":
            console.print("[dim]Closing browser and exiting.[/]")
            await close_browser()
            break

        console.print()
        summary = await agent.run(instruction)
        console.print(f"\n[bold green]Agent:[/] {summary}\n")
        console.rule(style="dim")

    from moodle_scraper import parser
    _print_token_summary(None, parser.TOKEN_USAGE)


async def run_course_mode():
    """Run the course navigator agent to find and open a specific course."""
    from moodle_scraper.agent import run_course_agent

    console.print(Panel(
        "",
        title="[bold cyan]Moodle Scraper -- Course Navigator[/]",
        border_style="cyan",
    ))

    course_name = input("Enter the course name to navigate to:\nCourse: ").strip()
    if not course_name:
        console.print("[yellow]No course name entered.[/]")
        return

    console.print(f"\n[bold]Navigating to course:[/] [italic]{course_name}[/]\n")

    summary = await run_course_agent(course_name)

    console.print(Panel(
        summary,
        title="[bold green]Course Navigator Finished[/]",
        border_style="green",
    ))


def main():
    """Parse arguments and run the appropriate mode."""
    if "--test-login" in sys.argv:
        asyncio.run(test_login())
    elif "--course" in sys.argv:
        asyncio.run(run_course_mode())
    elif "--agent" in sys.argv:
        asyncio.run(run_agent_mode())
    elif "--chat" in sys.argv:
        asyncio.run(run_chat_mode())
    elif "--prompt-file" in sys.argv:
        index = sys.argv.index("--prompt-file")
        if index + 1 >= len(sys.argv):
            print("Usage: python main.py --prompt-file path/to/prompt.txt")
        else:
            asyncio.run(run_prompt_file_mode(sys.argv[index + 1]))
    else:
        from moodle_scraper.mcp_server import mcp
        mcp.run()


if __name__ == "__main__":
    main()

