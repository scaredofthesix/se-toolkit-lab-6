"""Regression tests for agent.py.

These tests run agent.py as a subprocess and verify:
- Exit code is 0
- stdout contains valid JSON
- JSON has required fields: answer and tool_calls
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


AGENT_PATH = Path(__file__).parent.parent / "agent.py"


def run_agent(question: str) -> tuple[int, str, str]:
    """Run agent.py with a question.

    Args:
        question: The question to pass to the agent.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    result = subprocess.run(
        [sys.executable, str(AGENT_PATH), question],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


class TestAgentOutput:
    """Test suite for agent.py output validation."""

    def test_agent_returns_valid_json_with_required_fields(self):
        """Test that agent outputs valid JSON with 'answer' and 'tool_calls' fields."""
        question = "What is the capital of France?"

        returncode, stdout, stderr = run_agent(question)

        # Check exit code
        assert returncode == 0, f"Agent exited with code {returncode}, stderr: {stderr}"

        # Check stdout is not empty
        assert stdout.strip(), "Agent produced no output"

        # Check stdout is valid JSON
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Agent output is not valid JSON: {stdout[:200]}. Error: {e}")

        # Check required fields exist
        assert "answer" in data, f"Missing 'answer' field in output: {stdout[:200]}"
        assert "tool_calls" in data, f"Missing 'tool_calls' field in output: {stdout[:200]}"

        # Check field types
        assert isinstance(data["answer"], str), f"'answer' should be a string, got {type(data['answer'])}"
        assert isinstance(data["tool_calls"], list), f"'tool_calls' should be an array, got {type(data['tool_calls'])}"

        # Check answer is not empty
        assert len(data["answer"].strip()) > 0, "'answer' field is empty"
