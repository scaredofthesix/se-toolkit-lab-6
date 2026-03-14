# Agent Architecture - Task 2: The Documentation Agent

## Overview

This agent is a CLI that uses an **agentic loop** to call tools (`read_file`, `list_files`) for reading project documentation, then returns a structured JSON response with the answer, source reference, and all tool calls made.

## LLM Provider

**Provider:** OpenRouter  
**Model:** `meta-llama/llama-3.3-70b-instruct:free`  
**Why OpenRouter?**

- Works from Russia without VPN
- No credit card required
- Free tier with 50 requests/day
- Strong model for function calling

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
   - Loads configuration from `.env.agent.secret`
   - Defines tool schemas for function calling
   - Runs the agentic loop
   - Executes tools (`read_file`, `list_files`)
   - Extracts source references
   - Outputs JSON to stdout, debug info to stderr

2. **`.env.agent.secret`** — Configuration file (gitignored)
   - `LLM_API_KEY` — OpenRouter API key
   - `LLM_API_BASE` — `https://openrouter.ai/api/v1`
   - `LLM_MODEL` — Model name

3. **`AGENT.md`** — This documentation file

## Tools

### `read_file`

Read the contents of a file at the given path.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message.

**Security:** Rejects paths containing `..` to prevent directory traversal.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read the contents of a file at the given path",
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
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries (directories have trailing `/`).

**Security:** Rejects paths containing `..` to prevent directory traversal.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories at the given path",
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

## System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to explore the wiki directory structure
2. Use `read_file` to read relevant files and find answers
3. Look for section headers to identify specific sections
4. Include a source reference in the format `wiki/filename.md#section-anchor`
5. Return a final answer (no tool calls) when done

## How to Run

```bash
# Basic usage with wiki question
uv run agent.py "How do you resolve a merge conflict?"

# Example output
{
  "answer": "To resolve a merge conflict, edit the conflicting file...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

## Output Format

```json
{
  "answer": "<the LLM's answer>",
  "source": "wiki/filename.md#section-anchor",
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
- `source` (string, required): Reference to the wiki section (e.g., `wiki/git-workflow.md#resolving-merge-conflicts`)
- `tool_calls` (array, required): All tool calls made during the agentic loop

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing API key | Print error to stderr, exit code 1 |
| API timeout (>60s) | Print error to stderr, exit code 1 |
| HTTP error | Print status code and response to stderr, exit code 1 |
| Invalid path (traversal) | Return error as tool result |
| File not found | Return error as tool result |
| Max iterations (10) | Use whatever answer is available |

## Path Security

Both tools validate paths to prevent directory traversal:

- Reject any path containing `..`
- Reject absolute paths (must be relative)
- Verify the resolved path is within the project root

## Dependencies

- `httpx` — HTTP client for API calls
- `python-dotenv` — Load environment variables from `.env.agent.secret`

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- Agent exits with code 0
- stdout contains valid JSON
- JSON has `answer`, `source`, and `tool_calls` fields
- Tool calls are populated when tools are used
- Correct tools are called for specific questions

## Future Work (Task 3)

- Add `query_api` tool for backend LMS integration
- Add more domain-specific tools
- Improve source extraction with better section anchor generation
