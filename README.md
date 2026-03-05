# Automated Moodle Quiz Scraper

A fully automated tool that logs into a Moodle instance (including DFN-AAI SSO),
discovers courses and quizzes, scrapes quiz data (questions, answers, feedback, grades),
structures it using Azure OpenAI (GPT-4o), and exports results to XML, HTML, and screenshots.

The project supports two modes of operation:

1. **MCP server** -- an LLM client (Claude Desktop, VS Code Copilot) connects via Model
   Context Protocol and calls tools to drive the scraper.
2. **Azure OpenAI agent** -- a standalone tool-calling agent loop that uses GPT-4o to
   decide which browser actions to take, running without an external LLM client.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Project Structure](#2-project-structure)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Usage](#5-usage)
6. [Available Tools](#6-available-tools)
7. [Output](#7-output)
8. [Running Tests](#8-running-tests)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Requirements

- Python 3.11 or higher
- A Moodle instance you have student or teacher access to
- An Azure OpenAI resource with a `gpt-4o` deployment (vision-enabled)
- A virtual environment manager (venv or conda)

---

## 2. Project Structure

```
automated_moodle_scraper/
├── .github/
│   └── copilot-instructions.md   # Coding rules for Copilot
├── .env                           # Your secrets (never commit this)
├── .gitignore
├── main.py                        # Entry point (3 modes)
├── pyproject.toml                 # Project metadata and dependencies
├── requirements.txt
├── steps.md                       # Step-by-step development guide
├── README.md                      # This file
├── src/
│   └── moodle_scraper/
│       ├── __init__.py
│       ├── browser.py             # Playwright browser lifecycle
│       ├── auth.py                # DFN-AAI SSO login logic
│       ├── tools.py               # Shared tool implementations (single source of truth)
│       ├── agent.py               # Generic Agent class (Azure OpenAI loop)
│       ├── parser.py              # Azure OpenAI client wrapper
│       ├── models.py              # Pydantic data models (TODO)
│       ├── exporter.py            # XML, HTML, screenshot export (TODO)
│       ├── mcp_server.py          # MCP tool server (thin wrappers around tools.py)
│       └── utils.py               # Logging, timestamps, output paths
├── output/
│   └── screenshots/               # Captured screenshots
└── tests/
    ├── __init__.py
    ├── test_auth.py
    └── test_parser.py
```

---

## 3. Installation

### Step 1 -- Clone the repository

```bash
git clone https://github.com/your-username/automated_moodle_scraper.git
cd automated_moodle_scraper
```

### Step 2 -- Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
```

### Step 3 -- Install dependencies

```bash
pip install -e ".[dev]"
```

### Step 4 -- Install Playwright browsers

```bash
playwright install chromium
```

---

## 4. Configuration

Create a `.env` file in the project root with the following variables:

```dotenv
# Moodle credentials
MOODLE_BASE_URL=https://moodle2.uni-potsdam.de
MOODLE_USERNAME=your_username
MOODLE_PASSWORD=your_password

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Scraper behavior
HEADLESS=true                  # Set to false to watch the browser
OUTPUT_DIR=./output
LOG_LEVEL=INFO                 # DEBUG for verbose output
```

**Never commit `.env` to version control.** The `.gitignore` already excludes it.

---

## 5. Usage

The project has three run modes, all through `main.py`:

### MCP server mode (default)

Start the MCP server for external LLM clients (Claude Desktop, VS Code Copilot):

```bash
python main.py
```

Or use the MCP inspector to test tools interactively in the browser:

```bash
mcp dev src/moodle_scraper/mcp_server.py
```

To connect Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "moodle-scraper": {
      "command": "python",
      "args": ["main.py"],
      "cwd": "C:/path/to/automated_moodle_scraper"
    }
  }
}
```

### Azure OpenAI agent mode

Run the standalone agent that uses GPT-4o to decide which tools to call:

```bash
python main.py --agent
```

You will be prompted to enter a goal in plain English (e.g. "Log into Moodle and
list all my courses"). The agent calls tools step by step until the goal is done.

### Manual login test

Test that the browser can log into Moodle without any LLM involvement:

```bash
python main.py --test-login
```

This launches the browser, performs the DFN-AAI SSO login, takes a screenshot,
and waits for you to press Enter before closing.

---

## 6. Available Tools

All tools are defined once in `tools.py` and available in both MCP server and
agent modes. New tools are added in one place and automatically work everywhere.

### Currently implemented

| Tool | Description |
|---|---|
| `login` | Launch browser, clear cache, log into Moodle via DFN-AAI SSO |
| `navigate` | Navigate the browser to any URL |
| `take_screenshot` | Capture the current page as a PNG |
| `get_page_content` | Return visible text of the current page |
| `get_status` | Check if browser is open, logged in, and current URL |
| `close_browser` | Shut down the browser session |

### Planned (see `steps.md` for details)

| Tool | Description |
|---|---|
| `list_courses` | Discover all enrolled courses |
| `list_quizzes` | List quizzes in a given course |
| `scrape_quiz` | Scrape and parse one quiz |
| `export_to_xml` | Export quiz data to XML |
| `export_to_html` | Export quiz data to a readable HTML page |

### Agent-only tools

The standalone agent (via `--agent`) also has a `done` tool that signals the goal
is accomplished. This tool is managed by the `Agent` class, not by `tools.py`.

---

## 7. Output

All output is saved to the `output/` directory (configurable via `OUTPUT_DIR`).

### Screenshots (`output/screenshots/`)

Saved as `{label}_{YYYYMMDD_HHMMSS}.png`. Captured on login, by agent tool calls,
or on demand via the `take_screenshot` tool.

### XML and HTML export (planned)

Quiz data will be exportable to XML (Moodle-compatible format) and HTML
(human-readable page with all questions and answers).

---

## 8. Running Tests

```bash
pytest tests/ -v
```

To run a specific test file:

```bash
pytest tests/test_auth.py -v
```

---

## 9. Troubleshooting

### Login fails

- Confirm `MOODLE_BASE_URL` has no trailing slash.
- Set `HEADLESS=false` in `.env` to watch the browser and see what is happening.
- The login flow handles DFN-AAI SSO with the University of Potsdam IdP.
  If your Moodle uses a different SSO flow, update the selectors in `auth.py`.

### Azure OpenAI errors

- Confirm your deployment name matches `AZURE_OPENAI_DEPLOYMENT` exactly (case-sensitive).
- Confirm the deployment supports vision (GPT-4o does; GPT-3.5 does not).
- Check that your API key has not expired.

### Playwright errors

- Run `playwright install chromium` again if the browser binary is missing.
- On Windows, make sure no antivirus software is blocking Chromium from launching.

### Debug logging

Set `LOG_LEVEL=DEBUG` in your `.env` file for verbose output.
