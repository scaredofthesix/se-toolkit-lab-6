# Task 3: The System Agent - Implementation Plan

## Overview

Extend the Task 2 documentation agent with a `query_api` tool to interact with the deployed backend API. This enables the agent to answer questions about both static system facts (framework, ports, status codes) and data-dependent queries (item count, scores).

## New Tool: `query_api`

### Purpose

Call the deployed backend API to fetch data or test endpoints.

### Parameters

- `method` (string, required): HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (string, required): API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

### Returns

JSON string containing:
- `status_code`: HTTP status code
- `body`: Response body (parsed JSON or text)

### Authentication

- Use `LMS_API_KEY` from `.env.docker.secret`
- Include in `Authorization: Bearer <LMS_API_KEY>` header

### Function Schema (OpenAI format)

```json
{
  "name": "query_api",
  "description": "Call the backend API to fetch data or test endpoints. Use this for questions about database contents, API behavior, or status codes.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
      },
      "path": {
        "type": "string",
        "description": "API path (e.g., /items/, /analytics/completion-rate)"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

## Environment Variables

The agent must read all configuration from environment variables:

| Variable             | Purpose                              | Source              | Default                  |
|----------------------|--------------------------------------|---------------------|--------------------------|
| `LLM_API_KEY`        | LLM provider API key                 | `.env.agent.secret` | —                        |
| `LLM_API_BASE`       | LLM API endpoint URL                 | `.env.agent.secret` | —                        |
| `LLM_MODEL`          | Model name                           | `.env.agent.secret` | —                        |
| `LMS_API_KEY`        | Backend API key for query_api auth   | `.env.docker.secret`| —                        |
| `AGENT_API_BASE_URL` | Base URL for query_api               | `.env.docker.secret`| `http://localhost:42002` |

**Important:** The autochecker injects its own credentials. Never hardcode API keys or URLs.

## System Prompt Strategy

The system prompt must guide the LLM to choose the right tool:

1. **Wiki questions** (git workflow, SSH, processes) → `list_files` + `read_file`
2. **Source code questions** (framework, router modules, bugs) → `read_file` on code files
3. **API/data questions** (item count, status codes, analytics) → `query_api`
4. **Architecture questions** (request journey, ETL pipeline) → `read_file` on config files

Example system prompt additions:

```
You also have access to `query_api` for interacting with the backend API.

Use `query_api` when:
- Asked about database contents (e.g., "How many items...?")
- Asked about API behavior (e.g., "What status code...?")
- Asked to test an endpoint or fetch analytics data

Use `read_file` when:
- Asked about source code (e.g., "What framework does it use?")
- Asked to diagnose bugs (after getting an API error)
- Asked about configuration (docker-compose.yml, Dockerfile)

Use `list_files` + `read_file` when:
- Asked about wiki documentation
- Need to explore directory structure first
```

## Implementation Steps

1. **Add environment variable loading:**
   - Load `LMS_API_KEY` from `.env.docker.secret`
   - Load `AGENT_API_BASE_URL` (default: `http://localhost:42002`)

2. **Implement `query_api` function:**
   - Build URL from base + path
   - Add Authorization header with Bearer token
   - Handle GET/POST/PUT/DELETE methods
   - Return status_code and body as JSON string

3. **Add tool schema:**
   - Register alongside `read_file` and `list_files`

4. **Update system prompt:**
   - Add guidance for when to use each tool

5. **Update output format:**
   - `source` field is now optional (may be empty for API questions)

## Benchmark Questions

The agent must pass 10 local questions:

| # | Question | Expected Tool | Answer Type |
|---|----------|---------------|-------------|
| 0 | Wiki: protect a branch | `read_file` | keyword: branch, protect |
| 1 | Wiki: SSH connection | `read_file` | keyword: ssh, key, connect |
| 2 | Backend framework | `read_file` | keyword: FastAPI |
| 3 | API router modules | `list_files` | keyword: items, interactions, analytics |
| 4 | Item count in database | `query_api` | number > 0 |
| 5 | Status code without auth | `query_api` | keyword: 401, 403 |
| 6 | Completion-rate error | `query_api`, `read_file` | keyword: ZeroDivisionError |
| 7 | Top-learners bug | `query_api`, `read_file` | keyword: TypeError, None |
| 8 | Request lifecycle | `read_file` | LLM judge (≥4 hops) |
| 9 | ETL idempotency | `read_file` | LLM judge (external_id check) |

## Testing Strategy

Add 2 regression tests:

1. **Framework question:**
   - Question: "What framework does the backend use?"
   - Expected: `read_file` in tool_calls, answer contains "FastAPI"

2. **Database query question:**
   - Question: "How many items are in the database?"
   - Expected: `query_api` in tool_calls, answer contains a number

## Iteration Strategy

After initial implementation:

1. Run `uv run run_eval.py` to test all 10 questions
2. For each failure:
   - Read the feedback hint
   - Check which tool was called (or not called)
   - Adjust tool descriptions or system prompt
   - Re-run until passing
3. Document final score and lessons learned in `AGENT.md`

## File Changes

- `agent.py` — Add `query_api` tool, load LMS config, update system prompt
- `AGENT.md` — Document `query_api`, authentication, lessons learned (200+ words)
- `tests/test_agent.py` — Add 2 new test methods
- `plans/task-3.md` — This plan + benchmark results

## Benchmark Results

### Initial Run

**Score:** 0/10 passed

### First Failures and Diagnosis

| # | Question | Issue | Fix Strategy |
|---|----------|-------|--------------|
| 0 | Protect a branch | LLM hallucinates filename instead of using list_files first | Improve system prompt to emphasize list_files first |
| 1 | SSH connection | Not tested yet | — |
| 2 | Backend framework | Works (FastAPI) | — |
| 3 | API router modules | Not tested yet | — |
| 4 | Item count | LLM doesn't count items, just returns raw JSON | Add counting logic or improve prompt |
| 5 | Status code without auth | Not tested yet | — |
| 6 | Completion-rate error | Not tested yet | — |
| 7 | Top-learners bug | Not tested yet | — |
| 8 | Request lifecycle | Not tested yet | — |
| 9 | ETL idempotency | Not tested yet | — |

### Iteration Strategy

1. **Force list_files first:** Update system prompt to always start with `list_files("wiki")` for wiki questions
2. **Better answer extraction:** After reading file content, explicitly ask LLM to extract the answer
3. **Count items:** For database queries, prompt LLM to count the array length
4. **Test incrementally:** Run one question at a time with `uv run run_eval.py --index N`

### Lessons Learned

1. **LLM needs explicit guidance:** Simply having tools isn't enough — the system prompt must explicitly guide tool selection order
2. **Hallucination is a problem:** Free models may hallucinate filenames rather than exploring first
3. **Answer extraction is separate from tool use:** The LLM may call the right tool but fail to extract the answer properly
4. **Iterative development is key:** Run eval, diagnose, fix prompt, repeat
