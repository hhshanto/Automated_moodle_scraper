# Architecture Diagrams

Visual overview of everything implemented so far.

---

## 1. Module Architecture

Layered dependency structure: entry point, interface layer (MCP + Agent),
shared tools, infrastructure (browser, auth, parser), and support utilities.

```mermaid
graph TB
    subgraph Entry["main.py -- Entry Point"]
        M["main.py"]
    end

    subgraph Interfaces["Interface Layer"]
        MCP["mcp_server.py<br/><i>MCP tool server<br/>thin wrappers</i>"]
        AG["agent.py<br/><i>Agent class<br/>Azure OpenAI loop</i>"]
    end

    subgraph Core["Core Layer"]
        T["tools.py<br/><i>TOOL_REGISTRY<br/>single source of truth</i>"]
    end

    subgraph Infrastructure["Infrastructure Layer"]
        BR["browser.py<br/><i>Playwright lifecycle<br/>BrowserSession singleton</i>"]
        AU["auth.py<br/><i>DFN-AAI SSO<br/>login only</i>"]
        PA["parser.py<br/><i>Azure OpenAI<br/>client wrapper</i>"]
    end

    subgraph Support["Support Layer"]
        UT["utils.py<br/><i>logging, timestamps<br/>output directories</i>"]
    end

    M -->|"default"| MCP
    M -->|"--agent"| AG
    M -->|"--test-login"| BR
    M -->|"--test-login"| AU

    MCP --> T
    AG --> T
    AG --> PA

    T --> BR
    T --> AU
    T --> UT

    AU --> BR

    style Entry fill:#4a90d9,color:#fff
    style Interfaces fill:#f5a623,color:#fff
    style Core fill:#7ed321,color:#fff
    style Infrastructure fill:#9b59b6,color:#fff
    style Support fill:#95a5a6,color:#fff
```

---

## 2. Run Modes

Three ways to start the app: MCP server (default), standalone agent, manual login test.

```mermaid
flowchart TD
    START(["python main.py ..."])

    START --> CHECK{"sys.argv?"}

    CHECK -->|"--test-login"| TL["test_login()"]
    CHECK -->|"--agent"| AM["run_agent_mode()"]
    CHECK -->|"no args"| MCPRUN["mcp.run()"]

    subgraph TestLogin["Test Login Mode"]
        TL --> TL1["launch_browser()"]
        TL1 --> TL2["clear_cookies_and_cache()"]
        TL2 --> TL3["login_to_moodle()"]
        TL3 --> TL4{"Success?"}
        TL4 -->|Yes| TL5["take_screenshot()"]
        TL4 -->|No| TL6["Print error"]
        TL5 --> TL7["Wait for Enter"]
        TL7 --> TL8["close_browser()"]
        TL6 --> TL8
    end

    subgraph AgentMode["Agent Mode"]
        AM --> AM1["Prompt user for goal"]
        AM1 --> AM2["create_moodle_browser_agent()"]
        AM2 --> AM3["agent.run(goal)"]
        AM3 --> AM4["Azure OpenAI loop<br/>up to 20 steps"]
        AM4 --> AM5["Print summary"]
    end

    subgraph MCPMode["MCP Server Mode"]
        MCPRUN --> MCP1["FastMCP stdio server"]
        MCP1 --> MCP2["External LLM client<br/>calls tools via MCP"]
    end

    style START fill:#4a90d9,color:#fff
    style TestLogin fill:#e8f5e9
    style AgentMode fill:#fff3e0
    style MCPMode fill:#f3e5f5
```

---

## 3. DFN-AAI SSO Login Flow

Full Shibboleth login sequence: Moodle redirects to WAYF, JavaScript selects
University of Potsdam, IdP login form is filled, SAML assertion redirects back.

```mermaid
sequenceDiagram
    participant B as browser.py
    participant A as auth.py
    participant WAYF as DFN-AAI WAYF
    participant IDP as Uni Potsdam IdP
    participant M as Moodle

    Note over B,M: login_to_moodle(username, password, base_url)

    A->>B: active_session.page.goto(login_url)
    B->>M: GET /login/index.php
    M-->>WAYF: 302 Redirect to DFN-AAI

    Note over A,WAYF: _handle_sso_organisation_picker()
    A->>WAYF: wait_for_selector("#userIdPSelection")
    WAYF-->>A: Select element found
    A->>WAYF: JS: set select value to<br/>idp.uni-potsdam.de
    A->>WAYF: click("input[name='Select']")
    WAYF-->>IDP: 302 Redirect to IdP

    Note over A,IDP: _fill_sso_login_form()
    A->>IDP: wait_for_selector("#username")
    IDP-->>A: Login form loaded
    A->>IDP: fill("#username", username)
    A->>IDP: fill("#password", password)
    A->>IDP: click("button[type='submit']")
    IDP-->>M: SAML Assertion redirect

    Note over A,M: Verify login success
    A->>M: wait_for_url(base_url/**)
    M-->>A: Moodle dashboard URL
    A->>M: wait_for_selector(".usermenu")
    M-->>A: User menu found
    A->>B: wait_for_load_state("networkidle")
    A->>B: active_session.is_logged_in = True
    Note over A: Return True
```

---

## 4. Agent Loop (Azure OpenAI Tool-Calling)

The Agent sends messages + tool definitions to GPT-4o, receives tool calls,
dispatches them through tools.py, feeds results back, and repeats until done.

```mermaid
sequenceDiagram
    participant U as User
    participant AG as Agent.run()
    participant AO as Azure OpenAI<br/>(parser.py)
    participant T as tools.py<br/>execute_tool()
    participant BR as browser.py

    U->>AG: goal = "Log in and take screenshot"

    AG->>AO: messages = [system_prompt, user_goal]<br/>tools = TOOL_DEFINITIONS + done
    AO-->>AG: tool_calls: [{name: "login"}]

    AG->>T: execute_tool("login", {})
    T->>BR: launch_browser()
    T->>BR: clear_cookies_and_cache()
    T->>BR: login_to_moodle(...)
    BR-->>T: {"status": "logged_in", "page_title": "Dashboard"}
    T-->>AG: JSON result

    AG->>AO: messages += [assistant_tool_call, tool_result]
    AO-->>AG: tool_calls: [{name: "take_screenshot", args: {label: "dashboard"}}]

    AG->>T: execute_tool("take_screenshot", {label: "dashboard"})
    T->>BR: take_screenshot("dashboard_20260305.png")
    BR-->>T: {"file_path": "output/screenshots/..."}
    T-->>AG: JSON result

    AG->>AO: messages += [assistant_tool_call, tool_result]
    AO-->>AG: tool_calls: [{name: "done", args: {summary: "..."}}]

    AG-->>U: "Logged in and saved screenshot"
```

---

## 5. Tool Dispatch -- Single Source of Truth

Both MCP server and Agent converge on the same tools.py implementations.
Each tool maps down to browser.py, auth.py, or utils.py.

```mermaid
flowchart LR
    subgraph Callers["Who calls tools?"]
        MCP["mcp_server.py<br/>@mcp.tool()"]
        AGENT["agent.py<br/>Agent.run()"]
    end

    subgraph Registry["tools.py -- TOOL_REGISTRY"]
        direction TB
        LOGIN["login()"]
        NAV["navigate(url)"]
        SS["take_screenshot(label)"]
        GPC["get_page_content()"]
        GS["get_status()"]
        CB["close_browser()"]
    end

    subgraph Infra["Infrastructure"]
        BR["browser.py<br/>launch / navigate<br/>screenshot / close"]
        AUTH["auth.py<br/>login_to_moodle()"]
        UTIL["utils.py<br/>timestamps / paths"]
    end

    MCP -->|"await tools.login()"| LOGIN
    MCP -->|"await tools.navigate(url)"| NAV
    MCP -->|"await tools.take_screenshot(label)"| SS
    MCP -->|"await tools.get_page_content()"| GPC
    MCP -->|"await tools.get_status()"| GS
    MCP -->|"await tools.close_browser()"| CB

    AGENT -->|"execute_tool(name, args)"| LOGIN
    AGENT -->|"execute_tool(name, args)"| NAV
    AGENT -->|"execute_tool(name, args)"| SS
    AGENT -->|"execute_tool(name, args)"| GPC
    AGENT -->|"execute_tool(name, args)"| GS
    AGENT -->|"execute_tool(name, args)"| CB

    LOGIN --> BR
    LOGIN --> AUTH
    NAV --> BR
    SS --> BR
    SS --> UTIL
    GPC --> BR
    GS --> BR
    CB --> BR

    style Callers fill:#fff3e0
    style Registry fill:#e8f5e9
    style Infra fill:#e3f2fd
```
