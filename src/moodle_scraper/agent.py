"""
agent.py

Generic agent loop powered by Azure OpenAI. An Agent is configured with a
system prompt and a list of tool names (from tools.py). Different agents
can be created by varying the prompt and tool subset.

The default Moodle browser agent is created via create_moodle_browser_agent().
"""

import json
import logging

from moodle_scraper import parser
from moodle_scraper.tools import execute_tool, get_tool_definitions

logger = logging.getLogger(__name__)

MAX_STEPS = 20

# The "done" tool is always added by the Agent -- it is not in tools.py
# because it has no implementation (it just signals the loop to stop).
DONE_TOOL_SCHEMA = {
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
}


class Agent:
    """
    A generic agent that uses Azure OpenAI to decide which tools to call.

    Each agent is configured with a name, a system prompt, and a list of tool
    names from the shared TOOL_REGISTRY in tools.py.
    """

    def __init__(self, name: str, system_prompt: str, tool_names: list[str]) -> None:
        """
        Create a new agent.

        Args:
            name:          A human-readable name for this agent (used in logs).
            system_prompt: The system message that tells the model how to behave.
            tool_names:    List of tool names from tools.py to make available.
        """
        self.name = name
        self.system_prompt = system_prompt
        self.tool_definitions = get_tool_definitions(tool_names) + [DONE_TOOL_SCHEMA]

    async def run(self, goal: str) -> str:
        """
        Run the agent loop: send the goal to Azure OpenAI, execute tool calls,
        feed results back, repeat until the model calls 'done' or MAX_STEPS.

        Args:
            goal: Plain-English description of what to accomplish.

        Returns:
            A summary string of what the agent accomplished.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": goal},
        ]

        for step_number in range(1, MAX_STEPS + 1):
            logger.info("[%s] Step %d", self.name, step_number)

            response = parser.call_azure_openai(messages, tools=self.tool_definitions)
            response_message = response.choices[0].message

            if not response_message.tool_calls:
                final_text = response_message.content or "Agent finished without a summary."
                logger.info("[%s] Responded with text: %s", self.name, final_text)
                return final_text

            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_arguments = json.loads(tool_call.function.arguments)

                print(f"  Step {step_number}: calling {tool_name}({tool_arguments})")

                if tool_name == "done":
                    summary = tool_arguments.get("summary", "No summary provided.")
                    logger.info("[%s] Finished: %s", self.name, summary)
                    return summary

                tool_result = await execute_tool(tool_name, tool_arguments)
                logger.info("[%s] Tool result: %s", self.name, tool_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })

        return "Agent reached the maximum number of steps without completing the goal."


# ---------------------------------------------------------------------------
# Pre-built agents
# ---------------------------------------------------------------------------

MOODLE_BROWSER_SYSTEM_PROMPT = (
    "You are a browser automation agent for Moodle. "
    "You have tools to control a browser. Use them step by step to accomplish the user's goal. "
    "After each tool call you will see its result. Decide the next tool to call based on that result. "
    "When the goal is fully accomplished, call the 'done' tool with a summary. "
    "If you get stuck, call 'done' and explain what went wrong in the summary."
)

MOODLE_BROWSER_TOOLS = [
    "login",
    "navigate",
    "take_screenshot",
    "get_page_content",
    "get_status",
    "extract_links",
    "wait_on_page",
    "close_browser",
]


def create_moodle_browser_agent() -> Agent:
    """
    Create the default Moodle browser agent with all browser tools.

    Returns:
        An Agent instance configured for Moodle browser automation.
    """
    return Agent(
        name="moodle-browser",
        system_prompt=MOODLE_BROWSER_SYSTEM_PROMPT,
        tool_names=MOODLE_BROWSER_TOOLS,
    )


COURSE_NAVIGATOR_SYSTEM_PROMPT = (
    "You are a Moodle course navigation agent. Your job is to log into Moodle, "
    "find a specific course on the dashboard, navigate to it, and report what you see. "
    "Steps: 1) Call login to open the browser and log in. "
    "2) Call extract_links to find all links on the dashboard. "
    "3) Find the course link that matches the target course name. "
    "4) Call navigate with that URL to go to the course page. "
    "5) Call get_page_content to read the course page. "
    "6) Call take_screenshot to capture the course page. "
    "7) Call done with a summary of the course page contents. "
    "If the course is not found in the links, call done and explain that."
)

COURSE_NAVIGATOR_TOOLS = [
    "login",
    "navigate",
    "take_screenshot",
    "get_page_content",
    "get_status",
    "extract_links",
    "wait_on_page",
    "close_browser",
]


def create_course_navigator_agent() -> Agent:
    """
    Create a course navigator agent that logs in and navigates to a specific course.

    Returns:
        An Agent instance configured for course navigation.
    """
    return Agent(
        name="course-navigator",
        system_prompt=COURSE_NAVIGATOR_SYSTEM_PROMPT,
        tool_names=COURSE_NAVIGATOR_TOOLS,
    )


async def run_agent(goal: str) -> str:
    """
    Convenience function: create the default Moodle browser agent and run it.

    Args:
        goal: Plain-English description of what to accomplish.

    Returns:
        A summary string of what the agent accomplished.
    """
    agent = create_moodle_browser_agent()
    return await agent.run(goal)


async def run_course_agent(course_name: str) -> str:
    """
    Create the course navigator agent and navigate to the given course.

    Args:
        course_name: The name of the course to find and navigate to.

    Returns:
        A summary string of what the agent found on the course page.
    """
    agent = create_course_navigator_agent()
    goal = f"Log into Moodle and navigate to the course called '{course_name}'. Read the course page and take a screenshot."
    return await agent.run(goal)

