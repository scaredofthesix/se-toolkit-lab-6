# Agent Architecture - Task 1: Call an LLM from Code

## Overview

This agent is a simple CLI that connects to an LLM API, sends a user question, and returns a structured JSON response. It forms the foundation for the more complex agent with tools that will be built in Tasks 2–3.

## LLM Provider

**Provider:** OpenRouter  
**Model:** `meta-llama/llama-3.3-70b-instruct:free`  
**Why OpenRouter?**

- Works from Russia without VPN
- No credit card required
- Free tier with 50 requests/day
- Strong model for general knowledge questions

## Architecture

### Data Flow

```
User question (CLI arg) → agent.py → OpenRouter API → JSON response → stdout
```

### Components

1. **`agent.py`** — Main CLI entry point
   - Parses command-line arguments
   - Loads configuration from `.env.agent.secret`
   - Calls the LLM via HTTP POST
   - Outputs JSON to stdout, debug info to stderr

2. **`.env.agent.secret`** — Configuration file (gitignored)
   - `LLM_API_KEY` — OpenRouter API key
   - `LLM_API_BASE` — `https://openrouter.ai/api/v1`
   - `LLM_MODEL` — Model name (e.g., `openrouter/free`)

3. **`AGENT.md`** — This documentation file

## How to Run

```bash
# Basic usage
uv run agent.py "What does REST stand for?"

# Expected output
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "<the LLM's response>",
  "tool_calls": []
}
```

- `answer` (string, required): The LLM's answer to the question
- `tool_calls` (array, required): Empty for Task 1, will contain tool invocations in Task 2+

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing API key | Print error to stderr, exit code 1 |
| API timeout (>60s) | Print error to stderr, exit code 1 |
| HTTP error | Print status code and response to stderr, exit code 1 |
| Invalid response | Print error to stderr, exit code 1 |

## Dependencies

- `httpx` — HTTP client for API calls
- `python-dotenv` — Load environment variables from `.env.agent.secret`

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py
```

The test verifies:
- Agent exits with code 0
- stdout contains valid JSON
- JSON has `answer` and `tool_calls` fields

## Future Work (Tasks 2–3)

- Add tool definitions and a tool execution loop
- Integrate with the backend LMS API via `query_api` tool
- Add `read_file` and `list_files` tools for wiki access
- Expand the system prompt to guide tool usage
