# Copilot Instructions — Automated Moodle Quiz Scraper (MCP + LLM)

## Project Overview

Build a fully automated Moodle course quiz scraper that:
1. Logs into a Moodle instance using **username & password** (form-based login).
2. Navigates courses and discovers all quizzes.
3. Scrapes quiz pages including questions, answer options, correct answers, feedback, and grades.
4. Uses **Azure OpenAI** to parse, clean, and structure raw HTML/screenshot content into structured data.
5. Exposes all scraping capabilities as tools via a **Model Context Protocol (MCP) server**.
6. Exports results to **XML**, **html**, and **screenshots**.

---




---

## Environment Variables (`.env`)

```dotenv
# Moodle credentials
MOODLE_BASE_URL=https://your-moodle-instance.example.com
MOODLE_USERNAME=your_username
MOODLE_PASSWORD=your_password

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Scraper behavior
HEADLESS=true                  # Run browser headlessly
SCREENSHOT_ON_ERROR=true       # Save screenshot on failure
OUTPUT_DIR=./output
```


---

## Coding Rules

These rules apply to every file in this project. Follow them strictly.

### General

- No emojis anywhere — not in code, comments, docstrings, log messages, or output strings.
- Write code that a junior developer can read and understand without explanation.
- Prefer simple, flat code over clever, nested, or abstract code.
- If a function is hard to read at a glance, it needs to be simplified or split up.

### Naming

- Use long, descriptive names for variables, functions, and classes. Avoid abbreviations.
- Name variables after what they contain, not their type: `quiz_title` not `title_str`.
- Name functions after what they do: `fetch_quiz_page`, `parse_question_block`, `save_results_to_json`.
- Boolean variables must start with `is_`, `has_`, or `should_`: `is_logged_in`, `has_feedback`.

### Functions

- Every function does one thing only. If you can describe it with "and", split it.
- Keep functions short — aim for under 30 lines. Hard limit is 50 lines.
- All function parameters and return types must have type hints.
- Every public function must have a docstring that explains what it does, its parameters, and what it returns.

```python
async def fetch_quiz_page(page: Page, quiz_url: str) -> str:
    """
    Navigates to a Moodle quiz review page and returns the full page HTML.

    Args:
        page: The Playwright page instance to use for navigation.
        quiz_url: The full URL of the quiz review page.

    Returns:
        The full HTML content of the loaded page as a string.
    """
    await page.goto(quiz_url, wait_until="networkidle")
    return await page.content()
```

### Loops and Control Flow

- No nested loops unless absolutely unavoidable. Extract the inner body into a named function.
- No more than two levels of indentation inside a function body.
- Avoid complex list comprehensions with conditions. Use a plain `for` loop instead.
- Never use `lambda` for anything more than a one-word key function.
- Prefer early returns over deeply nested `if/else` chains.

```python
# Bad — nested loops, hard to follow
for course in courses:
    for quiz in course.quizzes:
        if quiz.is_active:
            for question in quiz.questions:
                process(question)

# Good — flat, each step is a clearly named function
active_quizzes = get_active_quizzes(courses)
for quiz in active_quizzes:
    process_all_questions(quiz)
```

### Error Handling

- Every `await` that touches the browser or network must be wrapped in `try/except`.
- Error messages must be specific: say what failed and why, not just "an error occurred".
- Use `logging.error(...)` for errors, `logging.info(...)` for progress, never `print()`.
- MCP tools must never raise exceptions — always return `{"error": "description"}`.

### Comments

- Write comments only when the code alone cannot explain the "why".
- Do not write comments that repeat what the code already says.
- Every module file must start with a one-paragraph docstring describing its purpose.

```python
# Bad — comment just repeats the code
# Loop through questions
for question in questions:
    ...

# Good — comment explains the why, not the what
# Moodle appends a session token to every form action, so we must
# re-fetch the login page right before submitting credentials.
await page.goto(login_url)
```

### Project-Specific Rules

- Never hard-code URLs, credentials, selectors, or file paths — always use constants or environment variables.
- All CSS selectors used in Playwright must be defined as named string constants at the top of the module, not inline in the code.
- All file paths must use `pathlib.Path`, never string concatenation.
- All Azure OpenAI calls must go through a single wrapper function in `parser.py` — never call the client directly from other modules.
- Screenshots must always be saved with a timestamp in the filename to avoid overwriting.
