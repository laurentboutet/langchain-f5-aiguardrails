# langchain-f5-aiguardrails

LangChain integration for **F5 AI Guardrails** — runtime security scanning of LLM prompts and responses.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

This package integrates F5 AI Guardrails (powered by CalypsoAI) into LangChain workflows. It supports two modes:

| Mode | Description | Use case |
|------|-------------|----------|
| **Inline proxy** | Routes LLM traffic through F5 proxy, scans inline | Production — single hop, Agentic Fingerprints |
| **Middleware** | Separate scan API calls before/after LLM | Flexible, works with any LLM provider |

Both modes:
- **Scan prompts** before they reach the LLM — detect prompt injection, PII leakage, toxic content
- **Scan responses** before they reach the user — detect data leakage, policy violations
- **Enforce or monitor** — block unsafe content or log it for observability

## Installation

```bash
pip install langchain-f5-aiguardrails
```

For inline proxy mode with OpenAI:

```bash
pip install "langchain-f5-aiguardrails[openai]"
```

## Quick Start

### Mode 1: Inline Proxy (recommended for production)

Routes LLM traffic through the F5 proxy for inline scanning + Agentic Fingerprints.

```python
from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager

# Create a session (all agents sharing this session appear in one CalypsoAI swimlane)
session = F5SessionManager(prefix="my-workflow")

# Drop-in replacement for ChatOpenAI — reads F5_GUARDRAIL_* env vars
llm = ChatF5OpenAI.from_env(
    session_manager=session,
    model="gpt-4o-mini",
)

# Use like any LangChain LLM
response = llm.invoke("What is the capital of France?")
print(response.content)
```

Required environment variables for inline proxy:

```bash
export F5_GUARDRAIL_API_KEY=your-calypsoai-token
export F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
export F5_GUARDRAIL_PROVIDER_OPENAI=your-provider-name
```

### Mode 2: Middleware (works with any LLM)

Intercepts LLM calls with separate before/after scan API calls.

```python
from langchain_f5_aiguardrails import F5GuardrailMiddleware

middleware = F5GuardrailMiddleware(
    api_key="your-f5-api-key",
    base_url="https://us1.calypsoai.app",
    mode="enforce",
)

# Use with LangChain agents
from langchain.agents import create_agent

agent = create_agent(
    model="openai:gpt-4o",
    tools=[],
    middleware=[middleware],
)

result = agent.invoke({"messages": [{"role": "user", "content": "Hello!"}]})
```

## How It Works

### Inline Proxy Mode

```
User message
    |
    v
+--------------------------------------------+
|  ChatF5OpenAI                              |
|  -> sends request to F5 proxy              |
|     with session ID header                 |
+--------------------------------------------+
    |
    v
  F5 AI Guardrails Proxy
  -> scans prompt inline
  -> if safe: forwards to OpenAI/LLM
  -> if blocked: returns error
    |
    v
  LLM response
  -> scans response inline
  -> if safe: returns to caller
    |
    v
Response returned to user
```

### Middleware Mode

```
User message
    |
    v
+--------------------------------------------+
|  before_model hook                         |
|  -> F5GuardrailClient.scan(prompt)         |
|  -> if blocked and mode="enforce": block   |
+--------------------------------------------+
    |
    v
  LLM call (OpenAI, Anthropic, etc.)
    |
    v
+--------------------------------------------+
|  after_model hook                          |
|  -> F5GuardrailClient.scan(response)       |
|  -> if blocked and mode="enforce": block   |
+--------------------------------------------+
    |
    v
Agent response returned to user
```

## Session Management (Inline Proxy Mode)

`F5SessionManager` manages the `x-cai-metadata-session-id` header sent with every request. CalypsoAI uses this header to group all LLM calls from the same workflow into a single **Agentic Fingerprint** swimlane.

```python
from langchain_f5_aiguardrails import F5SessionManager, ChatF5OpenAI

# Auto-generated UUID session ID with prefix
session = F5SessionManager(prefix="order-workflow")
print(session.session_id)  # "order-workflow-550e8400-e29b-..."

# Explicit session ID (e.g., from incoming request)
session = F5SessionManager(session_id="user-req-abc123")

# Multiple agents sharing the same session
llm_planner = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o")
llm_executor = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o-mini")
# Both appear in one CalypsoAI swimlane ↑
```

## Configuration (Middleware Mode)

### Direct Configuration

```python
middleware = F5GuardrailMiddleware(
    api_key="your-api-key",
    base_url="https://us1.calypsoai.app",
    mode="enforce",       # "enforce" | "monitor" | "off"
    fail_open=True,       # allow on API errors
    timeout=30,           # HTTP timeout in seconds
    project="my-project", # optional project ID
    verbose=False,        # detailed scanner results
    on_violation=my_callback,  # violation callback
    blocked_message="Content blocked by security policy.",
)
```

### Environment Variables

```bash
export F5_GUARDRAIL_API_KEY=your-api-key
export F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
export F5_GUARDRAIL_MODE=enforce
export F5_GUARDRAIL_FAIL_OPEN=true
export F5_GUARDRAIL_TIMEOUT=30
export F5_GUARDRAIL_PROJECT=my-project
```

```python
middleware = F5GuardrailMiddleware.from_env()
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | required | F5 AI Guardrails API key |
| `base_url` | `str` | `https://us1.calypsoai.app` | API base URL |
| `mode` | `str` | `enforce` | `enforce`, `monitor`, or `off` |
| `fail_open` | `bool` | `True` | Allow on API errors |
| `timeout` | `int` | `30` | HTTP timeout (seconds) |
| `project` | `str` | `None` | Default project ID |
| `verbose` | `bool` | `False` | Verbose scanner results |
| `on_violation` | `callable` | `None` | `(ScanResponse, ScanDirection) -> None` |
| `blocked_message` | `str` | *(default)* | Message on blocked content |

## Enforcement Modes

| Mode | Behavior |
|------|----------|
| `enforce` | Block violations — agent returns blocked message |
| `monitor` | Log violations and invoke callback; never blocks |
| `off` | Skip scanning entirely |

## Violation Callback

```python
from langchain_f5_aiguardrails import ScanResponse, ScanDirection

def my_callback(response: ScanResponse, direction: ScanDirection) -> None:
    print(f"Violation in {direction.value}: {response.outcome}")
    # Send to metrics, alerting, audit log, etc.

middleware = F5GuardrailMiddleware(
    api_key="key", mode="monitor", on_violation=my_callback,
)
```

## Development

```bash
git clone https://github.com/laurentboutet/langchain-f5-aiguardrails.git
cd langchain-f5-aiguardrails
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE) for details.
