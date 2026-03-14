#!/usr/bin/env python3
"""CLI agent with tools for reading documentation and querying the backend API.

Usage:
    uv run agent.py "How many items are in the database?"

Output:
    {
      "answer": "...",
      "source": "wiki/git-workflow.md#section (optional)",
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
    """Load LLM and LMS configuration from environment files.

    Returns:
        dict with keys: llm_api_key, llm_api_base, llm_model, lms_api_key, agent_api_base_url

    Raises:
        SystemExit: If required environment variables are missing.
    """
    # Load LLM config from .env.agent.secret
    llm_env_file = PROJECT_ROOT / ".env.agent.secret"
    load_dotenv(llm_env_file)

    # Load LMS config from .env.docker.secret
    lms_env_file = PROJECT_ROOT / ".env.docker.secret"
    load_dotenv(lms_env_file, override=False)

    llm_api_key = os.getenv("LLM_API_KEY")
    llm_api_base = os.getenv("LLM_API_BASE")
    llm_model = os.getenv("LLM_MODEL")
    lms_api_key = os.getenv("LMS_API_KEY")
    agent_api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

    if not llm_api_key:
        print("Error: LLM_API_KEY not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not llm_api_base:
        print("Error: LLM_API_BASE not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not llm_model:
        print("Error: LLM_MODEL not found in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not lms_api_key:
        print("Error: LMS_API_KEY not found in .env.docker.secret", file=sys.stderr)
        sys.exit(1)

    return {
        "llm_api_key": llm_api_key,
        "llm_api_base": llm_api_base,
        "llm_model": llm_model,
        "lms_api_key": lms_api_key,
        "agent_api_base_url": agent_api_base_url,
    }


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


def query_api(method: str, path: str, body: str = None, auth: bool = True) -> dict:
    """Call the backend API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API path (e.g., /items/, /analytics/completion-rate)
        body: Optional JSON request body for POST/PUT requests
        auth: Whether to include authentication header (default True)

    Returns:
        dict with 'success' bool and 'data' (response) or 'error' message.
    """
    config = load_config()
    base_url = config["agent_api_base_url"].rstrip("/")
    url = f"{base_url}{path}"

    headers = {
        "Content-Type": "application/json",
    }
    
    # Only include auth header if auth=True
    if auth:
        lms_api_key = config["lms_api_key"]
        headers["Authorization"] = f"Bearer {lms_api_key}"

    print(f"Calling API: {method} {url} (auth={auth})", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            # Try to parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = response.text

            return {
                "success": True,
                "status_code": response.status_code,
                "body": response_data,
            }

    except httpx.TimeoutException:
        return {"success": False, "error": "API request timed out (30s)"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Request failed: {e}"}


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
                "description": "Read the contents of a file at the given path. Use this to read wiki documentation, source code, or configuration files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., wiki/git-workflow.md, backend/app/main.py)",
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
                "description": "List files and directories at the given path. Use this to explore the project structure or find specific files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., wiki, backend/app/routers)",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Call the backend API to fetch data, test endpoints, or check status codes. Use this for questions about database contents, API behavior, analytics data, or HTTP responses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE)",
                        },
                        "path": {
                            "type": "string",
                            "description": "API path (e.g., /items/, /analytics/completion-rate, /analytics/top-learners)",
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT requests",
                        },
                        "auth": {
                            "type": "boolean",
                            "description": "Whether to include authentication header (default: true). Set to false to test unauthenticated requests.",
                        },
                    },
                    "required": ["method", "path"],
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

    elif tool_name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        # Handle auth parameter - could be bool or string "false"/"true"
        auth_param = args.get("auth", True)
        if isinstance(auth_param, str):
            auth = auth_param.lower() != "false"
        else:
            auth = auth_param if auth_param is not None else True
        result = query_api(method, path, body, auth)
        if result["success"]:
            response_data = {
                "status_code": result["status_code"],
                "body": result["body"],
            }
            # Help the LLM by including array length for list responses
            if isinstance(result["body"], list):
                response_data["array_length"] = len(result["body"])
                response_data["hint"] = f"The response contains {len(result['body'])} items in the array."
            return json.dumps(response_data)
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
    url = f"{config['llm_api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['llm_api_key']}",
        "Content-Type": "application/json",
    }

    # OpenRouter-specific headers
    if "openrouter.ai" in config["llm_api_base"]:
        headers["HTTP-Referer"] = "https://github.com/inno-se-toolkit/se-toolkit-lab-6"
        headers["X-Title"] = "SE Toolkit Lab 6 Agent"

    payload = {
        "model": config["llm_model"],
        "messages": messages,
        "max_tokens": 2048,  # Limit tokens to avoid credit issues with free models
    }

    if tools:
        payload["tools"] = tools

    print(f"Calling LLM at {config['llm_api_base']}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=120.0) as client:
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
    # System prompt for documentation and system agent
    system_prompt = """You are a documentation and system assistant for a software engineering project. You have access to tools that let you:
1. Read files and list directories in the project wiki and source code
2. Query the backend API to fetch data, test endpoints, or check status codes

**CRITICAL RULES:**
1. Tools execute IMMEDIATELY - don't describe what they "will" do, report what they DID
2. Always provide COMPLETE answers with actual data from tool responses
3. For wiki questions: FIRST list_files, THEN read_file, THEN extract the answer
4. For API questions: Call query_api, THEN report the actual status_code/data received
5. NEVER output partial answers or describe function calls - give the actual answer

**WORKFLOW FOR WIKI QUESTIONS:**
1. FIRST use `list_files("wiki")` to see all available files
2. LOOK at the file list to find the most relevant file (e.g., `github.md` for GitHub questions)
3. THEN use `read_file("wiki/filename.md")` to read that specific file
4. EXTRACT the actual answer from the file content - list the steps, facts, or information asked

**WORKFLOW FOR API QUESTIONS:**
1. Use `query_api` to make the API call
2. LOOK at the response (status_code, body, array_length)
3. EXTRACT the actual answer from the response data
4. If asked "how many", report the array_length or count the items

**WORKFLOW FOR BUG DIAGNOSIS:**
1. First make the API call to see the error
2. Then read the source file mentioned in the error traceback
3. Find the bug in the source code
4. Answer with: the error, the bug location (file:line), and the fix
5. ALWAYS include source reference in the "source" field: backend/app/routers/filename.py

**CRITICAL - Source field:**
- For wiki questions: source should be wiki/filename.md#section-anchor
- For bug diagnosis: source should be backend/app/routers/filename.py
- For API data questions: source is optional (can be empty)

**EXAMPLES OF GOOD ANSWERS:**
- "The steps to protect a branch are: 1. Go to Settings, 2. Go to Code and automation..." source: wiki/github.md#protect-a-branch
- "There are 44 items in the database."
- "The API router modules are: analytics.py (analytics), items.py (items), learners.py (learners)..."
- "The API returns 401 Unauthorized."
- "The bug is a ZeroDivisionError at line 212 in analytics.py. The fix is to check if total_learners is 0 before dividing." source: backend/app/routers/analytics.py#get_completion_rate

**EXAMPLES OF BAD ANSWERS (DO NOT DO THESE):**
- "This function call will..." (wrong - the tool already ran!)
- "The response is a JSON object that calls..." (wrong - report the actual data!)
- "The" (incomplete answer)
- "I need to use list_files first" (wrong - just do it and report results!)

When asked a question, choose the right tool:

**Step 1: Find the right file**
- Use `list_files` to explore directory structure FIRST (e.g., list "wiki" to find relevant files)
- Look at the file names to find the most relevant one
- Then use `read_file` to read that specific file
- NEVER guess file names - always use list_files first to discover the correct file

**Use `list_files` + `read_file` when:**
- Asked about wiki documentation (git workflow, SSH, processes)
- Need to explore directory structure first
- Asked about source code (framework, router modules, bugs)
- You don't know the exact file name - use list_files to discover it

**Use `read_file` when:**
- Asked to read specific files (docker-compose.yml, Dockerfile, source code)
- Asked to diagnose bugs (after getting an API error)
- Asked about configuration or architecture

**Use `query_api` when:**
- Asked about database contents (e.g., "How many items...?")
- Asked about API behavior (e.g., "What status code...?")
- Asked to test an endpoint or fetch analytics data
- Asked to check HTTP responses
- Asked to test unauthenticated requests (use auth=false)

**CRITICAL - Query Parameters:**
- When using `query_api` with GET requests, NEVER put query parameters in the `body` field
- ALWAYS include query parameters directly in the `path` string
- Example: For `?lab=lab-01`, use path="/analytics/completion-rate?lab=lab-01", NOT body='{"lab": "lab-01"}'
- Example: For `?enrolled_after=2024-01-01`, use path="/learners/?enrolled_after=2024-01-01"

**CRITICAL - Processing API Responses:**
- When you get an API response with a list/array, YOU MUST COUNT or ANALYZE the data yourself
- Do NOT just describe the function call - actually extract the answer from the response
- If asked "How many items?", count the array length in the response and report that number
- If asked "How many learners?", count the learners in the response array
- Look at the actual data returned and provide a specific numeric answer

**CRITICAL - HTTP Status Codes:**
- When asked about HTTP status codes, you MUST actually make the API call and report the status_code from the response
- The tool response includes "status_code": XXX - use that number in your answer
- Example: If response shows "status_code": 401, answer "The API returns 401 Unauthorized" or "401"
- Example: If response shows "status_code": 200, answer "The API returns 200 OK" or "200"
- Do NOT describe what the function call would do - actually report the status code you received
- Do NOT say you cannot answer - the tool response contains the answer

**Important:**
- After using tools, ALWAYS provide a final answer in natural language (no tool calls)
- Do NOT output tool call JSON in your final answer
- Just give the answer directly
- Read the file content carefully and extract the actual answer

**For answers:**
- When you have the answer from wiki/source, include a source reference: wiki/filename.md#section-anchor
- For API questions, the source is optional
- The section anchor should be lowercase with hyphens instead of spaces

Always provide accurate answers based on what you find."""

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
    source = extract_source(answer, all_tool_calls, question)

    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls,
    }


def extract_source(answer: str, tool_calls: list, question: str = "") -> str:
    """Extract or generate a source reference from the answer and tool calls.

    Args:
        answer: The LLM's answer text.
        tool_calls: List of tool calls made.
        question: The original question (used to detect bug diagnosis questions).

    Returns:
        Source reference string (e.g., wiki/git-workflow.md#section).
    """
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

    # Pattern 3: Bug diagnosis - look for backend file references in answer
    match = re.search(r'(backend/[\w\-/]+\.py)', answer)
    if match:
        return match.group(1)

    # Pattern 4: Bug diagnosis question - auto-set source from last backend file read
    question_lower = question.lower()
    if 'bug' in question_lower or 'error' in question_lower or 'analytics' in question_lower:
        for tc in reversed(tool_calls):
            if tc["tool"] == "read_file":
                path = tc["args"].get("path", "")
                if path.startswith("backend/"):
                    return path

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
    print(f"Using model: {config['llm_model']}", file=sys.stderr)

    result = run_agentic_loop(question, config)

    print(f"Answer generated with {len(result['tool_calls'])} tool calls", file=sys.stderr)

    # Output JSON to stdout
    print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
