# Task 1: Call an LLM from Code - Implementation Plan

## LLM Provider Choice

**Provider:** OpenRouter
**Model:** openrouter/free (auto-routes to available free models)
**Why:**

- Works from Russia without VPN
- No credit card required
- Multiple free models available
- Automatic fallback if one model is overloaded

## Architecture

### File Structure

- `agent.py` - Main CLI agent
- `.env.agent.secret` - LLM API configuration (gitignored)
- `AGENT.md` - Documentation
- `tests/test_agent.py` - Regression tests

### Code Flow

1. Parse command-line argument (question)
2. Load environment variables from `.env.agent.secret`
3. Prepare system prompt and user message
4. Call OpenRouter API via OpenAI-compatible client
5. Parse response and format JSON
6. Output only JSON to stdout, debug to stderr
7. Exit with code 0 on success

### Error Handling

- Missing API key → stderr message + exit 1
- API timeout (60s) → stderr message + exit 1
- Invalid JSON response → stderr message + exit 1

## Testing Strategy

- Subprocess test running `agent.py` with test questions
- Validate JSON output structure
- Verify `answer` and `tool_calls` fields present
