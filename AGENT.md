# Agent Architecture - Task 3: The System Agent

## Overview

This agent is a CLI that uses an **agentic loop** to call tools (`read_file`, `list_files`, `query_api`) for reading project documentation, querying the backend API, and returning a structured JSON response with the answer, optional source reference, and all tool calls made.

**Local Evaluation Results: 10/10 (100%)** ✅

## LLM Provider

**Provider:** OpenRouter
**Model:** `stepfun/step-3.5-flash:free` (or other free models)
**Why OpenRouter?**

- Works from Russia without VPN
- No credit card required
- Free tier with many models
- Strong models for function calling

**Alternative free models that work well:**
- `nvidia/nemotron-3-nano-30b-a3b:free`
- `google/gemma-3-12b-it:free`
- `meta-llama/llama-3.3-70b-instruct:free` (when available)

## Architecture

### Agentic Loop

```
Question → LLM (with tool schemas) → Response
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
            Has tool_calls?                           No tool_calls
                    │                                         │
                   Yes                                        │
                    │                                         │
                    ▼                                         │
            Execute each tool                                 │
                    │                                         │
                    ▼                                         │
            Append results as tool messages                   │
                    │                                         │
                    ▼                                         │
            Loop back to LLM (max 10 iterations)              │
                    │                                         │
                    └─────────────────────────────────────────┘
                                              │
                                              ▼
                                      Extract answer + source
                                              │
                                              ▼
                                      Output JSON and exit
```

### Data Flow

```
User question → agent.py → LLM (with tools) → tool calls → execute tools → 
LLM (with results) → final answer → JSON output
```

### Components

1. **`agent.py`** — Main CLI entry point
   - Parses command-line arguments
   - Loads configuration from `.env.agent.secret` and `.env.docker.secret`
   - Defines tool schemas for function calling
   - Runs the agentic loop
   - Executes tools (`read_file`, `list_files`, `query_api`)
   - Extracts source references
   - Outputs JSON to stdout, debug info to stderr

2. **`.env.agent.secret`** — LLM configuration (gitignored)
   - `LLM_API_KEY` — OpenRouter API key
   - `LLM_API_BASE` — `https://openrouter.ai/api/v1`
   - `LLM_MODEL` — Model name

3. **`.env.docker.secret`** — Backend configuration (gitignored)
   - `LMS_API_KEY` — Backend API key for `query_api` authentication
   - `AGENT_API_BASE_URL` — Backend API base URL (default: `http://localhost:42002`)

4. **`AGENT.md`** — This documentation file

## Tools

### `read_file`

Read the contents of a file at the given path.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`, `backend/app/main.py`)

**Returns:** File contents as a string, or an error message.

**Security:** Rejects paths containing `..` to prevent directory traversal.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read the contents of a file at the given path. Use this to read wiki documentation, source code, or configuration files.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root"
      }
    },
    "required": ["path"]
  }
}
```

### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`, `backend/app/routers`)

**Returns:** Newline-separated listing of entries (directories have trailing `/`).

**Security:** Rejects paths containing `..` to prevent directory traversal.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories at the given path. Use this to explore the project structure or find specific files.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root"
      }
    },
    "required": ["path"]
  }
}
```

### `query_api`

Call the backend API to fetch data, test endpoints, or check status codes.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required): API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` with Bearer token.

**Schema:**
```json
{
  "name": "query_api",
  "description": "Call the backend API to fetch data, test endpoints, or check status codes. Use this for questions about database contents, API behavior, analytics data, or HTTP responses.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE)"
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

## System Prompt Strategy

The system prompt guides the LLM to choose the right tool:

1. **Wiki questions** (git workflow, SSH, processes) → `list_files` + `read_file`
2. **Source code questions** (framework, router modules, bugs) → `read_file` on code files
3. **API/data questions** (item count, status codes, analytics) → `query_api`
4. **Architecture questions** (request journey, ETL pipeline) → `read_file` on config files

## How to Run

```bash
# Wiki question
uv run agent.py "How do you resolve a merge conflict?"

# Source code question
uv run agent.py "What framework does the backend use?"

# API question
uv run agent.py "How many items are in the database?"

# Example output
{
  "answer": "There are 42 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": [...]}"
    }
  ]
}
```

## Output Format

```json
{
  "answer": "<the LLM's answer>",
  "source": "wiki/filename.md#section-anchor (optional for API questions)",
  "tool_calls": [
    {
      "tool": "<tool_name>",
      "args": {"<arg>": "<value>"},
      "result": "<tool output>"
    }
  ]
}
```

- `answer` (string, required): The LLM's answer to the question
- `source` (string, optional): Reference to the wiki section (empty for API questions)
- `tool_calls` (array, required): All tool calls made during the agentic loop

## Environment Variables

| Variable             | Purpose                              | Source              | Default                  |
|----------------------|--------------------------------------|---------------------|--------------------------|
| `LLM_API_KEY`        | LLM provider API key                 | `.env.agent.secret` | —                        |
| `LLM_API_BASE`       | LLM API endpoint URL                 | `.env.agent.secret` | —                        |
| `LLM_MODEL`          | Model name                           | `.env.agent.secret` | —                        |
| `LMS_API_KEY`        | Backend API key for query_api auth   | `.env.docker.secret`| —                        |
| `AGENT_API_BASE_URL` | Base URL for query_api               | `.env.docker.secret`| `http://localhost:42002` |

**Important:** The autochecker injects its own credentials. Never hardcode API keys or URLs.

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing API key | Print error to stderr, exit code 1 |
| API timeout (>120s) | Print error to stderr, exit code 1 |
| HTTP error | Print status code and response to stderr, exit code 1 |
| Invalid path (traversal) | Return error as tool result |
| File not found | Return error as tool result |
| API request fails | Return error as tool result |
| Max iterations (10) | Use whatever answer is available |
| LLM rate limit | Print error to stderr, try alternative model |

## Path Security

Both file tools validate paths to prevent directory traversal:

- Reject any path containing `..`
- Reject absolute paths (must be relative)
- Verify the resolved path is within the project root

## Dependencies

- `httpx` — HTTP client for API calls (LLM and backend)
- `python-dotenv` — Load environment variables from `.env` files

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- Agent exits with code 0
- stdout contains valid JSON
- JSON has `answer`, `source` (optional), and `tool_calls` fields
- Tool calls are populated when tools are used
- Correct tools are called for specific questions

## Benchmark Results

The agent was tested against 10 local questions covering:
- Wiki lookup (branch protection, SSH)
- System facts (framework, router modules)
- Data queries (item count, status codes)
- Bug diagnosis (ZeroDivisionError, TypeError)
- Reasoning (request lifecycle, ETL idempotency)

### Lessons Learned

1. **Tool descriptions matter:** Initially the LLM would call `read_file` for API questions. Adding explicit guidance in the system prompt ("Use `query_api` when asked about database contents") fixed this.

2. **Anchor handling:** The LLM would include `#section` anchors in file paths. The `read_file` function now strips anchors before reading.

3. **Error messages help debugging:** Returning detailed error messages from tools helps the LLM recover and try alternative approaches.

4. **Source extraction is tricky:** The LLM doesn't always include source references in the expected format. The `extract_source` function uses regex patterns and fallbacks to find file references.

5. **Environment variable separation:** Keeping LLM and LMS credentials in separate files (`.env.agent.secret` vs `.env.docker.secret`) prevents confusion and matches the autochecker's injection strategy.

6. **Free model rate limits:** Free models on OpenRouter have strict rate limits. The agent works with many models (`stepfun/step-3.5-flash:free`, `nvidia/nemotron-3-nano-30b-a3b:free`, etc.), but switching models may be necessary when hitting limits.

7. **Array length hints help counting:** Adding `array_length` to API responses helps the LLM correctly count items without needing multiple tool calls.

8. **Auth parameter for testing:** Adding an `auth` parameter to `query_api` allows testing unauthenticated endpoints (e.g., checking 401 responses).

## Future Work

- Add more domain-specific tools (e.g., `search_code` for grep-like search)
- Improve source extraction with better section anchor generation
- Add support for multi-step tool chaining (e.g., query API error → read source → diagnose bug)
- Optimize for fewer tool calls by caching results
