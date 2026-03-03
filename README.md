# Automated Moodle Quiz Scraper

A fully automated tool that logs into a Moodle instance, discovers all courses and quizzes,
scrapes quiz data (questions, answers, feedback, grades), structures it using Azure OpenAI (GPT-4o),
and exports results to JSON, CSV, and screenshots.

All scraping capabilities are exposed as tools through a Model Context Protocol (MCP) server,
so any MCP-compatible client (e.g. Claude Desktop, VS Code Copilot) can drive the scraper directly.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Project Structure](#2-project-structure)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Running the MCP Server](#5-running-the-mcp-server)
6. [Available MCP Tools](#6-available-mcp-tools)
7. [Output Format](#7-output-format)
8. [Running Tests](#8-running-tests)
9. [Step-by-Step Workflow](#9-step-by-step-workflow)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Requirements

- Python 3.11 or higher
- A Moodle instance you have student or teacher access to
- An Azure OpenAI resource with a `gpt-4o` deployment (vision-enabled)
- Conda or a virtual environment manager

---

## 2. Project Structure

```
automated_moodle_scraper/
├── .github/
│   └── copilot-instructions.md   # Coding rules and architecture guide for Copilot
├── .env                           # Your secrets (never commit this)
├── .env.example                   # Template showing all required variables
├── .gitignore
├── pyproject.toml                 # Project metadata and dependencies
├── README.md                      # This file
├── src/
│   └── moodle_scraper/
│       ├── __init__.py
│       ├── auth.py                # Moodle login and session management
│       ├── navigator.py           # Course and quiz discovery
│       ├── scraper.py             # Quiz page scraping logic
│       ├── parser.py              # Azure OpenAI HTML and vision parsing
│       ├── models.py              # Pydantic data models
│       ├── exporter.py            # JSON, CSV, screenshot export
│       ├── mcp_server.py          # MCP server with all tools
│       └── utils.py               # Shared helpers (logging, timestamps, paths)
├── output/                        # All scraper output goes here (gitignored)
│   ├── json/
│   ├── csv/
│   └── screenshots/
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_scraper.py
    └── test_parser.py
```

---

## 3. Installation

### Step 1 -- Clone the repository

```bash
git clone https://github.com/your-username/automated_moodle_scraper.git
cd automated_moodle_scraper
```

### Step 2 -- Create a conda environment

```bash
conda create -n moodle_scraper python=3.11 -y
conda activate moodle_scraper
```

### Step 3 -- Install dependencies

```bash
pip install -e ".[dev]"
```

### Step 4 -- Install Playwright browsers

```bash
playwright install chromium
```

This downloads the Chromium browser that Playwright will control. You only need to do this once.

---

## 4. Configuration

### Step 1 -- Copy the environment template

```bash
cp .env.example .env
```

### Step 2 -- Fill in your values

Open `.env` and fill in all required fields:

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
HEADLESS=true
SCREENSHOT_ON_ERROR=true
OUTPUT_DIR=./output
```

**Never commit `.env` to version control.** The `.gitignore` already excludes it.

---

## 5. Running the MCP Server

### Development mode (recommended for first use)

```bash
mcp dev src/moodle_scraper/mcp_server.py
```

This starts the MCP server and opens an interactive inspector in the browser where you can
call each tool manually and inspect inputs and outputs.

### Production / client mode

Add the server to your MCP client configuration. For Claude Desktop, edit
`~/AppData/Roaming/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "moodle-scraper": {
      "command": "python",
      "args": ["-m", "moodle_scraper.mcp_server"],
      "cwd": "C:/path/to/automated_moodle_scraper/src"
    }
  }
}
```

---

## 6. Available MCP Tools

| Tool | Description |
|---|---|
| `login` | Authenticate to Moodle and start a browser session |
| `list_courses` | Return all enrolled courses for the logged-in user |
| `list_quizzes` | Return all quizzes for a given `course_id` |
| `scrape_quiz` | Scrape and parse one quiz by `quiz_id` |
| `scrape_all_quizzes` | Scrape every quiz across every course |
| `export_to_json` | Export scraped data for a quiz to a JSON file |
| `export_to_csv` | Export scraped data for a quiz to a CSV file |
| `take_screenshot` | Capture a screenshot of the current browser page |
| `get_status` | Return current session status (logged in, active page, etc.) |

---

## 7. Output Format

### JSON (`output/json/{course_id}_{quiz_id}.json`)

One file per quiz. Contains the full `Quiz` object including all questions, answer options,
correct answers, feedback, and points.

```json
{
  "quiz_id": "123",
  "quiz_title": "Week 3 Quiz",
  "course_id": "456",
  "course_name": "Introduction to Biology",
  "total_questions": 10,
  "scraped_at": "2026-03-03T14:22:00",
  "questions": [
    {
      "question_number": 1,
      "question_text": "What is the powerhouse of the cell?",
      "question_type": "multiple_choice",
      "answer_options": [
        { "text": "Mitochondria", "is_correct": true, "feedback": "Correct." },
        { "text": "Nucleus", "is_correct": false, "feedback": null }
      ],
      "correct_answer": "Mitochondria",
      "general_feedback": "The mitochondria produces ATP through cellular respiration.",
      "points": 1.0
    }
  ]
}
```

### CSV (`output/csv/{course_id}_{quiz_id}.csv`)

One row per question. Answer options and correct answers are pipe-separated.

| quiz_title | question_number | question_text | question_type | answer_options | correct_answers | points |
|---|---|---|---|---|---|---|
| Week 3 Quiz | 1 | What is the powerhouse... | multiple_choice | Mitochondria\|Nucleus | Mitochondria | 1.0 |

### Screenshots (`output/screenshots/`)

Saved as `{course_id}_{quiz_id}_{question_number}_{timestamp}.png`.
Captured automatically when vision-based parsing is used or when an error occurs.

---

## 8. Running Tests

```bash
pytest tests/ -v
```

To run a specific test file:

```bash
pytest tests/test_auth.py -v
```

Tests mock all browser and Azure OpenAI calls so no live credentials are needed.

---

## 9. Step-by-Step Workflow

This section describes what happens when you run the scraper end-to-end.

### Step 1 -- Start the session

Call the `login` tool. The browser launches (headless by default), navigates to the Moodle
login page, fills in your credentials, and verifies the session is active.

### Step 2 -- Discover courses

Call `list_courses`. The scraper navigates to `/my/courses.php` and extracts all enrolled
course names, IDs, and URLs.

### Step 3 -- Discover quizzes

Call `list_quizzes` with a `course_id`. The scraper opens the course page, finds all
activity links of type `quiz`, and returns a list of quiz titles, IDs, and URLs.

### Step 4 -- Scrape a quiz

Call `scrape_quiz` with a `quiz_id`. The scraper:
1. Navigates to the quiz review page with `showall=1` to load all questions at once.
2. Extracts raw HTML for each question block.
3. Attempts direct DOM extraction first (faster, no API cost).
4. Falls back to Azure OpenAI vision parsing if the DOM extraction is incomplete
   (e.g. MathJax formulas, image-based questions, unclear correct answer markers).
5. Returns a structured `Quiz` object.

### Step 5 -- Export results

Call `export_to_json` and/or `export_to_csv` with the `quiz_id`. Files are written to
`output/json/` and `output/csv/` respectively.

### Step 6 -- (Optional) Bulk scrape

Call `scrape_all_quizzes` to repeat steps 2-5 automatically for every course and quiz.
Results are saved to the output directory as each quiz finishes.

---

## 10. Troubleshooting

### Login fails

- Confirm `MOODLE_BASE_URL` has no trailing slash.
- Set `HEADLESS=false` to watch the browser and see what is happening.
- Some Moodle instances use SSO. Form-based login only works with the standard Moodle login page.

### Azure OpenAI errors

- Confirm your deployment name matches `AZURE_OPENAI_DEPLOYMENT` exactly (case-sensitive).
- Confirm the deployment supports vision (GPT-4o does; GPT-3.5 does not).
- Check that your API key has not expired.

### Playwright errors

- Run `playwright install chromium` again if the browser binary is missing.
- On Windows, make sure no antivirus software is blocking Chromium from launching.

### Output files are empty

- Check `output/screenshots/` for error screenshots that show what the page looked like.
- Enable debug logging: `LOG_LEVEL=DEBUG` in your `.env` file.
