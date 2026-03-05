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
main.py                (entry point -- 3 modes: MCP, --agent, --test-login)
    |
    +-- mcp_server.py  (MCP tool server -- external LLM clients call these)
    +-- agent.py       (Azure OpenAI agent loop -- standalone mode)
    |
    +-- parser.py      (Azure OpenAI client wrapper -- single entry point for all LLM calls)
    |
    +-- auth.py        (browser session, SSO login, navigation, screenshots)
    |
    +-- models.py      (Pydantic data models)
    +-- exporter.py    (export to XML, HTML, screenshots)
    +-- utils.py       (logging, timestamps, output directories)
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

## Step 2 -- auth.py [DONE]

**Goal:** Launch the browser, handle DFN-AAI SSO login, manage the session.

**File:** `src/moodle_scraper/auth.py`

### What was built

Moodle.UP uses DFN-AAI Shibboleth SSO. The login flow is:

1. Navigate to `{MOODLE_BASE_URL}/login/index.php` -- this redirects to the DFN-AAI WAYF page.
2. On the WAYF page, set the hidden `<select>` to "University of Potsdam" via JavaScript.
3. Click the "Select" submit button.
4. Fill username and password on the university IdP login form at `idp.uni-potsdam.de`.
5. Click "Login" -- Shibboleth redirects back to Moodle with an active session.

### CSS selector constants

```
LOGIN_SUCCESS_SELECTOR         = ".usermenu"
SSO_ORGANISATION_SELECT_SELECTOR = "#userIdPSelection"
SSO_ORGANISATION_SUBMIT_SELECTOR = "input[name='Select']"
SSO_ORGANISATION_VALUE         = "https://idp.uni-potsdam.de/idp/shibboleth"
SSO_USERNAME_SELECTOR          = "#username"
SSO_PASSWORD_SELECTOR          = "#password"
SSO_LOGIN_BUTTON_SELECTOR      = "button[type='submit']"
```

### Functions implemented

| Function | What it does |
|---|---|
| `launch_browser()` | Starts Chromium via Playwright, stores on `active_session` |
| `navigate_to_url(url)` | Navigates to any URL, returns page title |
| `take_screenshot(file_path)` | Saves a full-page PNG to disk |
| `clear_cookies_and_cache()` | Clears cookies, localStorage, sessionStorage |
| `login_to_moodle(username, password, base_url)` | Full SSO login flow, returns `True`/`False` |
| `close_browser()` | Closes browser and resets `active_session` |

Private helpers:

| Function | What it does |
|---|---|
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

## Step 4 -- agent.py [DONE]

**Goal:** A standalone Azure OpenAI agent loop that takes a plain-English goal,
decides which browser tools to call, executes them, and repeats until done.

**File:** `src/moodle_scraper/agent.py`

### Tools the agent can call

| Tool | Description |
|---|---|
| `login` | Launch browser and log into Moodle via SSO |
| `navigate` | Go to a specific URL |
| `take_screenshot` | Capture the current page as a PNG |
| `get_page_content` | Get the visible text of the current page (truncated to 4000 chars) |
| `get_status` | Check browser and login state |
| `close_browser` | Shut down the browser |
| `done` | Signal the goal is accomplished, with a summary |

### Key constants

- `MAX_STEPS = 20` -- the agent stops after 20 tool calls to prevent infinite loops.
- `SYSTEM_PROMPT` -- instructs the model to act as a browser automation agent.

### Functions implemented

| Function | What it does |
|---|---|
| `execute_tool_call(tool_name, tool_arguments)` | Dispatcher -- calls the right `_execute_*` function |
| `run_agent(goal)` | Main loop: send messages to Azure OpenAI, execute tool calls, repeat |

**Status:** Complete. Run with `python main.py --agent`.

---

## Step 5 -- mcp_server.py [DONE]

**Goal:** Expose browser capabilities as MCP tools so an external LLM client
(Claude Desktop, VS Code Copilot) can call them.

**File:** `src/moodle_scraper/mcp_server.py`

### Tools implemented

| Tool | Description |
|---|---|
| `login` | Launch browser, clear cache, log into Moodle |
| `take_screenshot` | Capture the current page as a PNG |
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
- Add each tool to both `mcp_server.py` (for MCP clients) and `agent.py`
  (for the standalone agent).
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
| Using `"div.que"` as a string inside `page.locator(...)` | Define a constant: `QUESTION_BLOCK_SELECTOR = "div.que"` |
| Building file paths with `output_dir + "/" + filename` | Use `pathlib`: `output_dir / filename` |
| Catching all exceptions silently | Log the error with context: `logging.error("...", error)` |
| Calling `configure_logging()` multiple times | Call it once at startup in `main.py` and `mcp_server.py` |
| Storing browser state in a local variable | Store it in the module-level `active_session` object |
| MCP tools raising exceptions | Always return `{"error": "description"}` instead |