# Development Guide -- Automated Moodle Quiz Scraper (MCP + LLM Agent)

This guide walks through building every module from scratch, in the correct order.
Each step has a clear goal, a list of functions to write, and a definition of done.

The project supports **two modes of operation**:

1. **MCP server** -- an LLM client (Claude Desktop, VS Code Copilot) connects via MCP
   and calls tools to accomplish goals.
2. **Azure OpenAI agent** -- a standalone tool-calling agent loop that uses
   `gpt-4o` to decide which browser actions to take.

Both modes share the same underlying browser/auth/parser/exporter modules.

---

## Prerequisites

Before writing any code, confirm you have:

- Python 3.11+ installed
- A virtual environment activated (`.venv`)
- All dependencies installed: `pip install -e ".[dev]"`
- Playwright browsers installed: `playwright install chromium`
- A `.env` file with all values filled in (see README)

---

## Architecture

```
main.py                   (entry point -- 3 modes: MCP, --agent, --test-login)
    |
    +-- mcp_server.py     (MCP tool server -- thin wrappers around tools.py)
    +-- agent.py          (generic Agent class -- Azure OpenAI tool-calling loop)
    |
    +-- tools.py          (single source of truth for all tool implementations)
    |
    +-- browser.py        (Playwright browser lifecycle: launch, navigate, screenshot, close)
    +-- auth.py           (DFN-AAI SSO login logic only)
    +-- parser.py         (Azure OpenAI client wrapper -- single entry point for all LLM calls)
    |
    +-- models.py         (Pydantic data models)
    +-- exporter.py       (export to XML, HTML, screenshots)
    +-- utils.py          (logging, timestamps, output directories)
```

Build from the bottom up. Do not start a layer until the layer below it is done.

---

## Step 1 -- utils.py [DONE]

**Goal:** Shared helpers that every module can import without circular dependencies.

**File:** `src/moodle_scraper/utils.py`

**Functions implemented:**

| Function | What it does |
|---|---|
| `get_output_directory()` | Returns `Path` to output dir from `OUTPUT_DIR` env var |
| `get_screenshot_directory()` | Returns `Path` to `output/screenshots/` |
| `build_timestamp_string()` | Returns current UTC time as `YYYYMMDD_HHMMSS` |
| `configure_logging()` | Sets up root logger from `LOG_LEVEL` env var |

**Status:** Complete. All four functions work.

---

## Step 2 -- browser.py + auth.py [DONE]

**Goal:** Split browser lifecycle and authentication into separate modules.

### browser.py -- Browser lifecycle

**File:** `src/moodle_scraper/browser.py`

Manages the Playwright browser: launching, navigating, screenshots, cookie
management, and shutdown. Has no knowledge of Moodle or authentication.

| Function | What it does |
|---|---|
| `launch_browser()` | Starts Chromium via Playwright, stores on `active_session` |
| `navigate_to_url(url)` | Navigates to any URL, waits for networkidle, returns page title |
| `take_screenshot(file_path)` | Saves a full-page PNG to disk |
| `get_page_text()` | Returns visible text of the current page (truncated to 4000 chars) |
| `clear_cookies_and_cache()` | Clears cookies, localStorage, sessionStorage |
| `close_browser()` | Closes browser and resets `active_session` |

### auth.py -- DFN-AAI SSO login

**File:** `src/moodle_scraper/auth.py`

Handles Moodle authentication through the DFN-AAI Shibboleth SSO flow.
Imports browser primitives from `browser.py`.

Moodle.UP uses DFN-AAI Shibboleth SSO. The login flow is:

1. Navigate to `{MOODLE_BASE_URL}/login/index.php` -- this redirects to the DFN-AAI WAYF page.
2. On the WAYF page, set the hidden `<select>` to "University of Potsdam" via JavaScript.
3. Click the "Select" submit button.
4. Fill username and password on the university IdP login form at `idp.uni-potsdam.de`.
5. Click "Login" -- Shibboleth redirects back to Moodle with an active session.

### CSS selector constants (auth.py)

```
LOGIN_SUCCESS_SELECTOR         = ".usermenu"
SSO_ORGANISATION_SELECT_SELECTOR = "#userIdPSelection"
SSO_ORGANISATION_SUBMIT_SELECTOR = "input[name='Select']"
SSO_ORGANISATION_VALUE         = "https://idp.uni-potsdam.de/idp/shibboleth"
SSO_USERNAME_SELECTOR          = "#username"
SSO_PASSWORD_SELECTOR          = "#password"
SSO_LOGIN_BUTTON_SELECTOR      = "button[type='submit']"
```

### Functions implemented (auth.py)

| Function | What it does |
|---|---|
| `login_to_moodle(username, password, base_url)` | Full SSO login flow, returns `True`/`False` |
| `_handle_sso_organisation_picker()` | Sets WAYF select value via JS, clicks Submit |
| `_fill_sso_login_form(username, password)` | Fills IdP form, clicks Login |

**Status:** Complete. Tested against live Moodle -- login succeeds.

---

## Step 3 -- parser.py [DONE]

**Goal:** Single wrapper for all Azure OpenAI API calls. No other module touches
the OpenAI client directly.

**File:** `src/moodle_scraper/parser.py`

### Functions implemented

| Function | What it does |
|---|---|
| `_get_client()` | Lazy singleton `AzureOpenAI` client |
| `_get_deployment_name()` | Reads `AZURE_OPENAI_DEPLOYMENT` from env |
| `call_azure_openai(messages, tools)` | Single entry point for all chat completions |

**Status:** Complete. Used by `agent.py` for the tool-calling loop.

---

## Step 4 -- tools.py + agent.py [DONE]

### tools.py -- Shared tool implementations

**Goal:** Single source of truth for all tool implementations. Both the MCP
server and the agent loop call these functions, so logic is never duplicated.

**File:** `src/moodle_scraper/tools.py`

| Function | What it does |
|---|---|
| `login()` | Launch browser, clear cache, log into Moodle via SSO |
| `navigate(url)` | Navigate the browser to any URL |
| `take_screenshot(label)` | Capture the current page as a timestamped PNG |
| `get_page_content()` | Get the visible text of the current page |
| `get_status()` | Check browser and login state |
| `close_browser()` | Shut down the browser session |
| `get_tool_definitions(tool_names)` | Build OpenAI-format tool schemas from the registry |
| `execute_tool(tool_name, tool_arguments)` | Look up and execute a tool by name |

Every tool function returns a plain `dict` (never raises). The `TOOL_REGISTRY`
maps tool names to their implementation functions and OpenAI schemas.

### agent.py -- Generic agent loop

**Goal:** A generic `Agent` class that takes a system prompt and a list of tool
names, then runs the Azure OpenAI tool-calling loop. New agents can be created
by varying the prompt and tool subset.

**File:** `src/moodle_scraper/agent.py`

| Class/Function | What it does |
|---|---|
| `Agent(name, system_prompt, tool_names)` | Creates an agent with a specific prompt and tool set |
| `Agent.run(goal)` | Runs the agent loop until done or MAX_STEPS reached |
| `create_moodle_browser_agent()` | Factory for the default Moodle browser agent |
| `run_agent(goal)` | Convenience function: creates default agent and runs it |

### Key constants

- `MAX_STEPS = 20` -- the agent stops after 20 tool calls.
- `MOODLE_BROWSER_SYSTEM_PROMPT` -- instructs the model to act as a browser automation agent.
- `MOODLE_BROWSER_TOOLS` -- the list of tools available to the default agent.
- `DONE_TOOL_SCHEMA` -- always appended to every agent's tool list.

**Status:** Complete. Run with `python main.py --agent`.

---

## Step 5 -- mcp_server.py [DONE]

**Goal:** Expose browser capabilities as MCP tools so an external LLM client
(Claude Desktop, VS Code Copilot) can call them. Each MCP tool is a thin
wrapper around the shared implementation in `tools.py`.

**File:** `src/moodle_scraper/mcp_server.py`

### Tools implemented

| Tool | Description |
|---|---|
| `login` | Launch browser, clear cache, log into Moodle |
| `navigate` | Navigate the browser to any URL |
| `take_screenshot` | Capture the current page as a PNG |
| `get_page_content` | Get the visible text of the current page |
| `get_status` | Check browser/login state and current URL |
| `close_browser` | Shut down the browser session |

### How to run

```bash
python main.py           # Start as MCP server (stdio transport)
mcp dev src/moodle_scraper/mcp_server.py   # MCP inspector in browser
```

**Status:** Complete. Basic tools work.

---

## Step 6 -- main.py [DONE]

**Goal:** Single entry point with three run modes.

**File:** `main.py`

| Command | Mode |
|---|---|
| `python main.py` | Start MCP server (for LLM clients) |
| `python main.py --agent` | Start Azure OpenAI agent loop |
| `python main.py --test-login` | Manual login test (no LLM) |

**Status:** Complete.

---

## Step 7 -- models.py [TODO]

**Goal:** Define Pydantic data models for all structured data in the project.

**File:** `src/moodle_scraper/models.py`

### Models to build

1. **`AnswerOption`** -- one answer choice
   - `text: str` -- the answer text
   - `is_correct: bool` -- whether this is the correct answer
   - `feedback: str | None` -- optional feedback for this specific option

2. **`QuizQuestion`** -- one question
   - `question_number: int`
   - `question_text: str`
   - `question_type: str` -- one of: `multiple_choice`, `true_false`, `short_answer`, `essay`, `matching`
   - `answer_options: list[AnswerOption]`
   - `correct_answer: str | None` -- the correct answer text, if known
   - `general_feedback: str | None`
   - `points: float | None`

3. **`Quiz`** -- a full quiz
   - `quiz_id: str`
   - `quiz_title: str`
   - `quiz_url: str`
   - `questions: list[QuizQuestion]`
   - `scraped_at: str` -- timestamp of when the quiz was scraped

4. **`Course`** -- a course with its quizzes
   - `course_id: str`
   - `course_name: str`
   - `course_url: str`
   - `quizzes: list[Quiz]`

### Definition of done

- All models import cleanly: `from moodle_scraper.models import Quiz, Course`
- You can instantiate each model with sample data
- Models use `pydantic.BaseModel`

---

## Step 8 -- Add navigation tools to MCP server and agent [TODO]

**Goal:** Add tools that the LLM can call to discover courses and quizzes.
These tools use the browser session from `auth.py` to navigate pages and
extract links. The LLM decides which pages to visit and what to do with the data.

### New MCP tools to add

| Tool | Description | Returns |
|---|---|---|
| `navigate_to_url(url)` | Navigate the browser to any URL | Page title |
| `get_page_content()` | Return visible text of the current page | Text (truncated) |
| `list_courses()` | Navigate to My Courses page and extract course links | List of `{course_id, course_name, url}` |
| `list_quizzes(course_url)` | Navigate to a course and extract quiz links | List of `{quiz_title, quiz_url}` |

### Implementation notes

- `list_courses` navigates to `{MOODLE_BASE_URL}/my/courses.php`, extracts all course
  links from the page. CSS selectors will need to be discovered by inspecting the
  live Moodle page.
- `list_quizzes` navigates to a given course URL and looks for quiz activity links.
  Moodle uses `.activity.quiz` as a class but the exact selectors may vary by theme.
- Add each tool to `tools.py` with an entry in `TOOL_REGISTRY`.
  The MCP server and agent will pick them up automatically.
- If a tool cannot find expected elements, return an `{"error": "..."}` dict
  instead of raising.

### Definition of done

- `list_courses` returns enrolled courses when tested against live Moodle
- `list_quizzes` returns quiz titles and URLs for a known course
- Both MCP server and standalone agent can use these tools

---

## Step 9 -- Add quiz scraping tools [TODO]

**Goal:** Add tools that navigate to a quiz review page, extract each question
block, and use Azure OpenAI to parse the content into structured `QuizQuestion` objects.

### New parser functions to add

| Function | What it does |
|---|---|
| `parse_question_html(html, question_number)` | Send question HTML to Azure OpenAI, return `QuizQuestion` |
| `parse_question_screenshot(image_path, question_number)` | Send a screenshot to Azure OpenAI vision, return `QuizQuestion` |

### New MCP tools to add

| Tool | Description | Returns |
|---|---|---|
| `scrape_quiz(quiz_url)` | Navigate to the quiz review page, extract all questions | `Quiz` dict with questions |
| `scrape_all_quizzes(course_url)` | Scrape every quiz in a course | List of `Quiz` dicts |

### Implementation approach

1. Navigate to the quiz main page.
2. Find the latest attempt review link.
3. Navigate to the review page with `showall=1`.
4. Extract each question block (`.que` elements).
5. For each question block:
   - Try DOM-based extraction first (BeautifulSoup, no LLM call).
   - Fall back to `parse_question_html` if DOM extraction is incomplete.
   - Fall back to `parse_question_screenshot` if HTML parsing fails.
6. Return the assembled `Quiz` object.

### Error handling

- If one question fails to parse, log the error and continue to the next.
- If the review page fails to load, return `{"error": "..."}`.
- Never let one bad question crash the entire scrape.

### Definition of done

- A known quiz is scraped with the correct number of questions
- Each question has `question_text`, `answer_options`, and `correct_answer` (when available)
- The LLM fallback is only triggered when DOM extraction is incomplete

---

## Step 10 -- exporter.py [TODO]

**Goal:** Export scraped quiz data to XML, HTML, and screenshots.

**File:** `src/moodle_scraper/exporter.py`

### Functions to build

| Function | What it does |
|---|---|
| `save_quiz_to_xml(quiz: Quiz) -> Path` | Export as Moodle XML format |
| `save_quiz_to_html(quiz: Quiz) -> Path` | Export as a readable HTML page |
| `save_quiz_screenshots(page, quiz: Quiz) -> list[Path]` | Save per-question screenshots |

### New MCP tools to add

| Tool | Description | Returns |
|---|---|---|
| `export_to_xml(quiz_id)` | Export a scraped quiz to XML | File path |
| `export_to_html(quiz_id)` | Export a scraped quiz to HTML | File path |

### In-memory quiz store

`mcp_server.py` needs a module-level dict to hold scraped quiz results between
tool calls:

```python
scraped_quizzes: dict[str, Quiz] = {}
```

### Definition of done

- `save_quiz_to_xml` produces a valid XML file
- `save_quiz_to_html` produces a readable HTML page with all questions and answers
- Screenshots are saved with timestamps in the filename

---

## Step 11 -- End-to-End Smoke Test [TODO]

Run this sequence manually using the MCP inspector or `--agent` mode:

```
1. login()                          -> {"status": "logged_in"}
2. list_courses()                   -> {"courses": [...]}
3. list_quizzes(course_url="...")   -> {"quizzes": [...]}
4. scrape_quiz(quiz_url="...")      -> {"quiz_id": ..., "questions": [...]}
5. export_to_xml(quiz_id="...")     -> {"file_path": "output/..."}
6. export_to_html(quiz_id="...")    -> {"file_path": "output/..."}
```

Verify the output files exist and contain the correct data.

---

## Step 12 -- Final Checklist [TODO]

Before marking the project complete, verify every item below.

### Code quality

- [ ] No `print()` calls anywhere (except `main.py` user prompts) -- only `logging`
- [ ] No emojis in any file
- [ ] Every public function has a docstring with Args and Returns
- [ ] All type hints are present on parameters and return values
- [ ] No function exceeds 50 lines
- [ ] No hardcoded URLs, passwords, selectors (outside their constant definitions), or file paths

### Tests

- [ ] `pytest tests/ -v` passes with no failures
- [ ] Tests cover: login success, login failure, HTML parsing, question count

### Functionality

- [ ] Login works against a live Moodle instance (DFN-AAI SSO)
- [ ] All enrolled courses are discovered
- [ ] All quizzes in a course are listed
- [ ] A quiz is scraped with correct questions, answers, and feedback
- [ ] XML and HTML export files are generated correctly
- [ ] Screenshots are saved with timestamps in the filename

### Security

- [ ] `.env` is listed in `.gitignore`
- [ ] No credentials or API keys appear anywhere in source code
- [ ] `output/` is listed in `.gitignore`

---

## Common Mistakes to Avoid

| Mistake | Correct approach |
|---|---|
| Calling `AzureOpenAI` directly in `agent.py` or `mcp_server.py` | All LLM calls go through `parser.py` only |
| Duplicating tool logic in `agent.py` and `mcp_server.py` | Define tools once in `tools.py`, use `TOOL_REGISTRY` |
| Putting browser lifecycle code in `auth.py` | Browser lifecycle lives in `browser.py`, login logic in `auth.py` |
| Using `"div.que"` as a string inside `page.locator(...)` | Define a constant: `QUESTION_BLOCK_SELECTOR = "div.que"` |
| Building file paths with `output_dir + "/" + filename` | Use `pathlib`: `output_dir / filename` |
| Catching all exceptions silently | Log the error with context: `logging.error("...", error)` |
| Calling `configure_logging()` multiple times | Call it once at startup in `main.py` and `mcp_server.py` |
| Storing browser state in a local variable | Store it in the module-level `active_session` object in `browser.py` |
| MCP tools raising exceptions | Always return `{"error": "description"}` instead |