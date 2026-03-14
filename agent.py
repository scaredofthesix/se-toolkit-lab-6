#!/usr/bin/env python3
"""CLI agent that calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {"answer": "Representational State Transfer.", "tool_calls": []}

All debug output goes to stderr. Only valid JSON goes to stdout.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def load_config() -> dict:
    """Load LLM configuration from .env.agent.secret.

    Returns:
        dict with keys: api_key, api_base, model

    Raises:
        SystemExit: If required environment variables are missing.
    """
    # Load from .env.agent.secret in project root
    env_file = Path(__file__).parent / ".env.agent.secret"
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


def call_llm(question: str, config: dict) -> str:
    """Call the LLM API and return the answer.

    Args:
        question: The user's question.
        config: LLM configuration (api_key, api_base, model).

    Returns:
        The LLM's answer as a string.

    Raises:
        SystemExit: If the API call fails or times out.
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    # OpenRouter-specific headers (optional, but helps with routing)
    if "openrouter.ai" in config["api_base"]:
        headers["HTTP-Referer"] = "https://github.com/inno-se-toolkit/se-toolkit-lab-6"
        headers["X-Title"] = "SE Toolkit Lab 6 Agent"

    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Answer questions concisely and accurately.",
            },
            {"role": "user", "content": question},
        ],
    }

    print(f"Calling LLM at {config['api_base']}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract answer from OpenAI-compatible response
            choices = data.get("choices", [])
            if not choices:
                print("Error: No choices in LLM response", file=sys.stderr)
                sys.exit(1)

            answer = choices[0].get("message", {}).get("content", "")
            if not answer:
                print("Error: Empty answer from LLM", file=sys.stderr)
                sys.exit(1)

            return answer

    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP error {e.response.status_code}: {e.response.text[:200]}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Request failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py <question>", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    # Load configuration
    config = load_config()
    print(f"Using model: {config['model']}", file=sys.stderr)

    # Call LLM
    answer = call_llm(question, config)
    print(f"Answer received", file=sys.stderr)

    # Output JSON to stdout
    result = {"answer": answer, "tool_calls": []}
    print(json.dumps(result))

    sys.exit(0)


if __name__ == "__main__":
    main()
