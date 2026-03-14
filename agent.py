#!/usr/bin/env python3
"""CLI agent with tools for reading project documentation.

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output:
    {
      "answer": "...",
      "source": "wiki/git-workflow.md#resolving-merge-conflicts",
      "tool_calls": [...]
    }

All debug output goes to stderr. Only valid JSON goes to stdout.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory (where agent.py is located)
PROJECT_ROOT = Path(__file__).parent


def load_config() -> dict:
    """Load LLM configuration from .env.agent.secret.

    Returns:
        dict with keys: api_key, api_base, model

    Raises:
        SystemExit: If required environment variables are missing.
    """
    env_file = PROJECT_ROOT / ".env.agent.secret"
    load_dotenv(env_file)

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        print("Error: LLM_API_KEY not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not api_base:
        print("Error: LLM_API_BASE not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not model:
        print("Error: LLM_MODEL not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    return {"api_key": api_key, "api_base": api_base, "model": model}


def is_safe_path(path: str) -> bool:
    """Check if a path is safe (no directory traversal).

    Args:
        path: The path to validate.

    Returns:
        True if safe, False if it contains '..' or is absolute.
    """
    if ".." in path or path.startswith("/") or path.startswith("\\"):
        return False
    return True


def read_file(path: str) -> dict:
    """Read the contents of a file.

    Args:
        path: Relative path from project root (may include #section anchor).

    Returns:
        dict with 'success' bool and 'content' or 'error' message.
    """
    # Strip any section anchor from the path
    if "#" in path:
        path = path.split("#")[0]

    if not is_safe_path(path):
        return {"success": False, "error": f"Invalid path: {path} (directory traversal not allowed)"}

    full_path = PROJECT_ROOT / path

    if not full_path.exists():
        return {"success": False, "error": f"File not found: {path}"}

    if not full_path.is_file():
        return {"success": False, "error": f"Not a file: {path}"}

    try:
        content = full_path.read_text(encoding="utf-8")
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": f"Error reading file: {e}"}


def list_files(path: str) -> dict:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root (may include #section anchor).

    Returns:
        dict with 'success' bool and 'entries' list or 'error' message.
    """
    # Strip any section anchor from the path
    if "#" in path:
        path = path.split("#")[0]

    if not is_safe_path(path):
        return {"success": False, "error": f"Invalid path: {path} (directory traversal not allowed)"}

    full_path = PROJECT_ROOT / path

    if not full_path.exists():
        return {"success": False, "error": f"Directory not found: {path}"}

    if not full_path.is_dir():
        return {"success": False, "error": f"Not a directory: {path}"}

    try:
        entries = []
        for entry in sorted(full_path.iterdir()):
            # Skip hidden files and directories
            if entry.name.startswith("."):
                continue
            # Add trailing slash for directories
            if entry.is_dir():
                entries.append(f"{entry.name}/")
            else:
                entries.append(entry.name)
        return {"success": True, "entries": entries}
    except Exception as e:
        return {"success": False, "error": f"Error listing directory: {e}"}


def get_tool_schemas() -> list:
    """Return the tool schemas for OpenAI function calling.

    Returns:
        List of tool schema dictionaries.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file at the given path. Use this to read wiki documentation or other project files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., wiki/git-workflow.md)",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at the given path. Use this to explore the project structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., wiki)",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
    ]


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result as a string.

    Args:
        tool_name: Name of the tool to execute.
        args: Arguments for the tool.

    Returns:
        String representation of the tool result.
    """
    print(f"Executing tool: {tool_name} with args: {args}", file=sys.stderr)

    if tool_name == "read_file":
        path = args.get("path", "")
        result = read_file(path)
        if result["success"]:
            return result["content"]
        else:
            return f"Error: {result['error']}"

    elif tool_name == "list_files":
        path = args.get("path", "")
        result = list_files(path)
        if result["success"]:
            return "\n".join(result["entries"])
        else:
            return f"Error: {result['error']}"

    else:
        return f"Error: Unknown tool: {tool_name}"


def call_llm(messages: list, config: dict, tools: list = None) -> dict:
    """Call the LLM API and return the response.

    Args:
        messages: List of message dictionaries.
        config: LLM configuration.
        tools: Optional list of tool schemas.

    Returns:
        dict with 'content' and 'tool_calls' keys.

    Raises:
        SystemExit: If the API call fails or times out.
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    # OpenRouter-specific headers
    if "openrouter.ai" in config["api_base"]:
        headers["HTTP-Referer"] = "https://github.com/inno-se-toolkit/se-toolkit-lab-6"
        headers["X-Title"] = "SE Toolkit Lab 6 Agent"

    payload = {
        "model": config["model"],
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools

    print(f"Calling LLM at {config['api_base']}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                print("Error: No choices in LLM response", file=sys.stderr)
                sys.exit(1)

            message = choices[0].get("message", {})
            content = message.get("content", "")

            # Parse tool calls if present
            tool_calls = []
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    if tc.get("type") == "function":
                        func = tc.get("function", {})
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append({
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "arguments": args,
                        })

            return {"content": content, "tool_calls": tool_calls}

    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP error {e.response.status_code}: {e.response.text[:200]}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Request failed: {e}", file=sys.stderr)
        sys.exit(1)


def run_agentic_loop(question: str, config: dict) -> dict:
    """Run the agentic loop with tool execution.

    Args:
        question: The user's question.
        config: LLM configuration.

    Returns:
        dict with 'answer', 'source', and 'tool_calls' keys.
    """
    # System prompt for documentation agent
    system_prompt = """You are a documentation assistant for a software engineering project. You have access to tools that let you read files and list directories in the project wiki.

When asked a question:
1. Use `list_files` to explore the wiki directory structure if needed
2. Use `read_file` to read relevant wiki files and find the answer
3. Look for section headers (lines starting with # or ##) to identify specific sections
4. When you have the answer, respond with a final message (no tool calls) that includes:
   - The answer to the question
   - A source reference in the format: wiki/filename.md#section-anchor
   - The section anchor should be lowercase with hyphens instead of spaces

Always provide a source reference when you find an answer in a file."""

    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    tool_schemas = get_tool_schemas()
    all_tool_calls = []

    iteration = 0
    while iteration < MAX_TOOL_CALLS:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---", file=sys.stderr)

        # Call LLM
        response = call_llm(messages, config, tools=tool_schemas)
        content = response["content"]
        tool_calls = response["tool_calls"]

        # If no tool calls, we have the final answer
        if not tool_calls:
            print(f"LLM returned final answer (no tool calls)", file=sys.stderr)
            break

        # Process tool calls
        for tool_call in tool_calls:
            print(f"Tool call: {tool_call['name']}({tool_call['arguments']})", file=sys.stderr)

            # Execute the tool
            result = execute_tool(tool_call["name"], tool_call["arguments"])

            # Record the tool call with result
            all_tool_calls.append({
                "tool": tool_call["name"],
                "args": tool_call["arguments"],
                "result": result,
            })

            # Add tool response to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

        # Add assistant message with tool calls
        assistant_message = {"role": "assistant", "content": content}
        if tool_calls:
            # Format tool calls for the API
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"]),
                    },
                }
                for tc in tool_calls
            ]
        messages.append(assistant_message)

    # Extract answer and source from final content
    answer = content.strip() if content else ""
    source = extract_source(answer, all_tool_calls)

    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls,
    }


def extract_source(answer: str, tool_calls: list) -> str:
    """Extract or generate a source reference from the answer and tool calls.

    Args:
        answer: The LLM's answer text.
        tool_calls: List of tool calls made.

    Returns:
        Source reference string (e.g., wiki/git-workflow.md#section).
    """
    # Look for source pattern in answer (e.g., "wiki/file.md#section")
    import re

    # Pattern 1: Full reference with anchor
    match = re.search(r'(wiki/[\w\-/]+\.md#[\w\-]+)', answer)
    if match:
        return match.group(1)

    # Pattern 2: File reference without anchor
    match = re.search(r'(wiki/[\w\-/]+\.md)', answer)
    if match:
        # Try to find a section in the answer
        section_match = re.search(r'##?\s+([A-Za-z][A-Za-z0-9\s\-:]*)', answer)
        if section_match:
            section = section_match.group(1).strip().lower().replace(" ", "-").replace(":", "")
            # Remove non-alphanumeric characters except hyphens
            section = re.sub(r'[^a-z0-9\-]', '', section)
            return f"{match.group(1)}#{section}"
        return match.group(1)

    # Fallback: use the last file read
    for tc in reversed(tool_calls):
        if tc["tool"] == "read_file":
            path = tc["args"].get("path", "")
            if path.startswith("wiki/"):
                return path

    return ""


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py <question>", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    config = load_config()
    print(f"Using model: {config['model']}", file=sys.stderr)

    result = run_agentic_loop(question, config)

    print(f"Answer generated with {len(result['tool_calls'])} tool calls", file=sys.stderr)

    # Output JSON to stdout
    print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
