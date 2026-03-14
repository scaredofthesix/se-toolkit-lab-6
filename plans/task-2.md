# Task 2: The Documentation Agent - Implementation Plan

## Overview

Transform the Task 1 agent into a documentation agent that can read the project wiki using two tools: `read_file` and `list_files`. The agent will use an agentic loop to iteratively call tools until it finds an answer.

## Tool Definitions

### `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:** Reject paths containing `../` to prevent directory traversal.

**Function schema (OpenAI format):**
```json
{
  "name": "read_file",
  "description": "Read the contents of a file at the given path",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root (e.g., wiki/git-workflow.md)"
      }
    },
    "required": ["path"]
  }
}
```

### `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries.

**Security:** Reject paths containing `../` to prevent directory traversal.

**Function schema (OpenAI format):**
```json
{
  "name": "list_files",
  "description": "List files and directories at the given path",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., wiki)"
      }
    },
    "required": ["path"]
  }
}
```

## Agentic Loop

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

**Loop logic:**
1. Send user question + system prompt + tool schemas to LLM
2. Parse response:
   - If `tool_calls` present → execute tools, append results, repeat (max 10 iterations)
   - If no `tool_calls` → extract answer from `content`, output JSON
3. Track all tool calls for the `tool_calls` output field

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki directory structure
2. Use `read_file` to read relevant files
3. Find the answer and include a source reference (file path + section anchor)
4. Return the final answer without tool calls when done

Example system prompt:
```
You are a documentation assistant. You have access to a project wiki via tools.

When asked a question:
1. First use `list_files` to explore the wiki directory structure
2. Then use `read_file` to read relevant files
3. Find the answer and note the source file path
4. If the answer is in a specific section, include a section anchor (e.g., wiki/git-workflow.md#resolving-merge-conflicts)
5. When you have the answer, respond with the final answer (no tool calls)

Always include the source field in your final answer.
```

## Output Format

```json
{
  "answer": "<the LLM's answer>",
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

## Path Security

Both tools must validate paths:
- Reject any path containing `../` (directory traversal)
- Reject absolute paths (must be relative)
- Ensure resolved path is within project root

Implementation:
```python
def is_safe_path(path: str) -> bool:
    if ".." in path or path.startswith("/"):
        return False
    return True
```

## Error Handling

- File not found → return error message as tool result
- Permission denied → return error message
- Invalid path (traversal attempt) → return error message
- LLM timeout → exit with error
- Max iterations (10) → use whatever answer is available

## Testing Strategy

Add 2 regression tests:

1. **Test with merge conflict question:**
   - Question: "How do you resolve a merge conflict?"
   - Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test with wiki listing question:**
   - Question: "What files are in the wiki?"
   - Expected: `list_files` in tool_calls

## File Changes

- `agent.py` — Add tool definitions, agentic loop, source extraction
- `AGENT.md` — Document tools and agentic loop architecture
- `tests/test_agent.py` — Add 2 new test methods
