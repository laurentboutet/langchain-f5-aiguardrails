# Integration Strategies for F5 AI Guardrails with LangChain

> How to integrate an external guardrail service into LangChain agent workflows — strategies, trade-offs, and our recommended approach.

---

## Table of Contents

- [Integration Strategies for F5 AI Guardrails with LangChain](#integration-strategies-for-f5-ai-guardrails-with-langchain)
  - [Table of Contents](#table-of-contents)
  - [1. Why External Guardrails?](#1-why-external-guardrails)
  - [2. Strategy 1: Middleware (Recommended)](#2-strategy-1-middleware-recommended)
    - [How It Works](#how-it-works)
    - [Advantages](#advantages)
    - [Disadvantages](#disadvantages)
    - [When to Use](#when-to-use)
  - [3. Strategy 2: Wrapper Chains](#3-strategy-2-wrapper-chains)
    - [How It Works](#how-it-works-1)
    - [Advantages](#advantages-1)
    - [Disadvantages](#disadvantages-1)
    - [When to Use](#when-to-use-1)
  - [4. Strategy 3: Custom LLM Proxy](#4-strategy-3-custom-llm-proxy)
    - [How It Works](#how-it-works-2)
    - [Advantages](#advantages-2)
    - [Disadvantages](#disadvantages-2)
    - [When to Use](#when-to-use-2)
  - [5. Strategy 4: Tool-Level Guards](#5-strategy-4-tool-level-guards)
    - [How It Works](#how-it-works-3)
    - [Advantages](#advantages-3)
    - [Disadvantages](#disadvantages-3)
    - [When to Use](#when-to-use-3)
  - [6. Comparison Matrix](#6-comparison-matrix)
  - [7. Our Approach: F5GuardrailMiddleware](#7-our-approach-f5guardrailmiddleware)
    - [Architecture](#architecture)
    - [Key Design Decisions](#key-design-decisions)
    - [Data Flow](#data-flow)
  - [8. Production Considerations](#8-production-considerations)
    - [Latency Impact](#latency-impact)
    - [Connection Management](#connection-management)
    - [Observability](#observability)
  - [9. Enforcement Modes](#9-enforcement-modes)
    - [Mode Selection Guidelines](#mode-selection-guidelines)
  - [10. Error Handling \& Fail-Open/Closed](#10-error-handling--fail-openclosed)
    - [Fail-Open (Default)](#fail-open-default)
    - [Fail-Closed](#fail-closed)
    - [Error Categories](#error-categories)
  - [Further Reading](#further-reading)

---

## 1. Why External Guardrails?

LLMs have inherent risks that traditional security tools (WAFs, API gateways) cannot detect:

| Risk | Description | Traditional Tools | AI Guardrails |
|------|-------------|------------------|---------------|
| **Prompt injection** | User tricks the LLM into ignoring instructions | ❌ Cannot detect | ✅ Detects semantic attacks |
| **PII leakage** | LLM outputs personal data from training/RAG | ❌ Cannot detect | ✅ Scans for PII patterns |
| **Toxic content** | LLM generates harmful, biased, or offensive text | ❌ Cannot detect | ✅ Toxicity classifiers |
| **Restricted topics** | LLM provides medical, legal, financial advice | ❌ Cannot detect | ✅ Topic enforcement |
| **Data exfiltration** | Attacker extracts internal data through prompts | ❌ Cannot detect | ✅ Content analysis |

**F5 AI Guardrails** provides a centralized, model-agnostic security layer that evaluates both prompts and responses against configurable policies. The question is: how do we integrate it into LangChain?

---

## 2. Strategy 1: Middleware (Recommended)

### How It Works

LangChain's middleware system provides dedicated hooks (`before_model`, `after_model`) that run at precisely the right moments in the agent loop. Our middleware intercepts every LLM call and sends the content to F5 AI Guardrails for scanning.

```
User → [before_model: scan prompt] → LLM → [after_model: scan response] → User
              │                                       │
              ▼                                       ▼
       F5 AI Guardrails                        F5 AI Guardrails
```

### Advantages

- **Zero changes to agent code** — add/remove by toggling middleware
- **Catches every LLM call** — including multi-turn agent loops
- **Clean separation of concerns** — security logic is isolated
- **Standard LangChain pattern** — well-documented, well-supported
- **Composable** — stack with other middleware (logging, rate limiting)
- **Both sync and async** — first-class support for both patterns

### Disadvantages

- Requires LangChain middleware support (available in latest versions)
- Adds latency per LLM call (two scan API calls per round-trip)

### When to Use

✅ **Always the first choice** for LangChain agent workflows. This is the canonical pattern.

---

## 3. Strategy 2: Wrapper Chains

### How It Works

Wrap the LLM in a custom chain that scans before and after:

```python
from langchain_core.runnables import RunnableLambda

def scan_and_call(messages):
    # Pre-scan
    prompt = messages[-1].content
    pre_result = guardrail_client.scan(prompt)
    if pre_result.outcome == "blocked":
        return AIMessage("Blocked by policy.")
    
    # Call LLM
    response = llm.invoke(messages)
    
    # Post-scan
    post_result = guardrail_client.scan(response.content)
    if post_result.outcome == "blocked":
        return AIMessage("Response blocked by policy.")
    
    return response

guarded_llm = RunnableLambda(scan_and_call)
```

### Advantages

- Works with older LangChain versions (no middleware needed)
- Full control over the scanning flow

### Disadvantages

- **Couples security logic to business logic** — harder to maintain
- **Doesn't catch tool calls** — only wraps the direct LLM invocation
- **Breaks composability** — every chain needs to be wrapped individually
- **Manual async handling** — must implement async separately

### When to Use

⚠️ Only when middleware is not available (legacy LangChain versions).

---

## 4. Strategy 3: Custom LLM Proxy

### How It Works

Instead of calling the LLM directly, route all traffic through F5 AI Guardrails as a proxy (inline moderator pattern):

```
LangChain → F5 Guardrails Proxy → LLM
                    │
                    ├── Scan prompt
                    ├── Forward to LLM (if safe)
                    ├── Scan response
                    └── Return to LangChain (if safe)
```

### Advantages

- **Completely transparent** — LangChain doesn't know the guardrail exists
- **Covers all use cases** — any LLM call goes through the proxy
- **No code changes** — just change the LLM endpoint URL

### Disadvantages

- **Infrastructure overhead** — requires a proxy service deployment
- **Single point of failure** — proxy outage = no LLM access
- **Less flexibility** — harder to have per-agent policies
- **No LangChain state access** — proxy can't read agent context

### When to Use

⚠️ When you need organization-wide guardrails at the network level, independent of any framework. Not specific to LangChain.

---

## 5. Strategy 4: Tool-Level Guards

### How It Works

Use `wrap_tool_call` to scan tool inputs and outputs:

```python
@wrap_tool_call
def guard_tool_calls(request, handler):
    # Scan tool arguments
    tool_input = json.dumps(request.tool_call["args"])
    pre_result = guardrail_client.scan(tool_input)
    
    if pre_result.outcome == "blocked":
        return ToolMessage("Tool call blocked by policy.", ...)
    
    # Execute tool
    result = handler(request)
    
    # Scan tool output
    if isinstance(result, ToolMessage):
        post_result = guardrail_client.scan(result.content)
        if post_result.outcome == "blocked":
            return ToolMessage("Tool output blocked by policy.", ...)
    
    return result
```

### Advantages

- **Granular control** — scan specific tool calls
- **Catches tool-specific risks** — SQL injection in DB tools, etc.
- **Complementary** — use alongside middleware for defense-in-depth

### Disadvantages

- **Doesn't cover LLM calls** — only tools
- **More complex** — tool results use `Command(update=...)` pattern
- **Scope-limited** — each tool needs its own security context

### When to Use

✅ **As a complement** to middleware, for tools that handle sensitive operations (database queries, email sending, code execution).

> **Note:** F5 AI Guardrails does not currently support tool/MCP call scanning. This strategy is reserved for future capability.

---

## 6. Comparison Matrix

| Criteria | Middleware | Wrapper Chains | LLM Proxy | Tool Guards |
|----------|-----------|---------------|-----------|-------------|
| **Covers LLM calls** | ✅ | ✅ | ✅ | ❌ |
| **Covers tool calls** | ❌ (future) | ❌ | ❌ | ✅ |
| **Zero code changes** | ✅ | ❌ | ✅ | ❌ |
| **Agent state access** | ✅ | Partial | ❌ | ✅ |
| **Composable** | ✅ | ❌ | N/A | ✅ |
| **Async support** | ✅ | Manual | N/A | ✅ |
| **Production-ready** | ✅ | ⚠️ | ✅ | ⚠️ |
| **Framework coupling** | LangChain | LangChain | None | LangChain |

**Recommendation:** Use **Strategy 1 (Middleware)** as the primary integration, with **Strategy 4 (Tool Guards)** as a future enhancement for defense-in-depth.

---

## 7. Our Approach: F5GuardrailMiddleware

Our implementation follows Strategy 1 with these design principles:

### Architecture

```python
class F5GuardrailMiddleware(AgentMiddleware):
    """
    LangChain middleware for F5 AI Guardrails.
    
    Scans prompts and responses via the F5 AI Guardrails scan API,
    blocking or logging violations based on the configured mode.
    """
```

### Key Design Decisions

1. **Class-based middleware** — uses `AgentMiddleware` base class for clean structure
2. **Async-first HTTP client** — uses `httpx` for both sync and async support
3. **Self-contained configuration** — no global state, no monkey-patching
4. **Pydantic models** — type-safe request/response handling matching the F5 API schema
5. **Fail-open by default** — if the guardrail API is unreachable, allow the request (configurable)
6. **Violation callbacks** — extensible hooks for logging, metrics, alerting
7. **Environment variable support** — production deployment via `from_env()` class method

### Data Flow

```
before_model(state, runtime):
    1. Extract latest user message from state["messages"]
    2. Call F5 API: POST /backend/v1/scans with input=message
    3. Check result.outcome:
       - "cleared" → return None (continue)
       - "flagged"/"blocked" + mode="enforce" → return {"jump_to": "end"}
       - "flagged"/"blocked" + mode="monitor" → log + return None
       - "redacted" → optionally use redactedInput

after_model(state, runtime):
    1. Extract latest AI message from state["messages"]
    2. Call F5 API: POST /backend/v1/scans with input=response
    3. Same outcome handling as above
```

---

## 8. Production Considerations

### Latency Impact

Each LLM call adds two scan API round-trips (prompt + response). Typical impact:

| Scan API latency | Total added per LLM call | Impact |
|-----------------|-------------------------|--------|
| 50ms | ~100ms | Negligible |
| 200ms | ~400ms | Noticeable for real-time chat |
| 500ms+ | ~1s+ | Consider async or monitor-only mode |

**Mitigation strategies:**
- Use `monitor` mode for latency-sensitive paths (log only, don't block)
- Configure appropriate timeouts (default: 30s)
- Use connection pooling (httpx manages this automatically)

### Connection Management

The `F5GuardrailClient` manages HTTP connections via `httpx`:
- Connection pooling for persistent connections
- Proper lifecycle management (open on first use, close on middleware disposal)
- Timeout configuration (connect timeout + read timeout)

### Observability

Built-in logging and extensible callbacks:

```python
middleware = F5GuardrailMiddleware(
    api_key_request="...",
    api_key_response="...",
    base_url="https://us1.calypsoai.app",
    mode="enforce",
    on_violation=lambda result, direction: 
        metrics.increment("guardrail.violation", tags={"direction": direction, "outcome": result.outcome}),
)
```

---

## 9. Enforcement Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **`enforce`** | Block violations — agent returns a "blocked" message | Production enforcement |
| **`monitor`** | Log violations + invoke callback; never blocks | Policy tuning, staging environments |
| **`off`** | Skip scanning entirely | Development, disabled guardrails |

### Mode Selection Guidelines

- **Start with `monitor`** — see what would be blocked without impacting users
- **Switch to `enforce`** — once policies are tuned and false-positive rate is acceptable
- **Use `off`** — only during local development to avoid API calls

---

## 10. Error Handling & Fail-Open/Closed

### Fail-Open (Default)

When `fail_open=True` and the F5 API is unreachable:
- The request is **allowed** to proceed
- A warning is logged
- The `on_violation` callback is **not** invoked (no violation occurred)

This is the recommended default because a guardrail outage should not block all AI functionality.

### Fail-Closed

When `fail_open=False` and the F5 API is unreachable:
- The request is **blocked**
- An error is logged
- The agent returns a safe fallback message

Use this for high-security environments where any unscanned content is unacceptable.

### Error Categories

| Error | Fail-Open | Fail-Closed |
|-------|-----------|-------------|
| Network timeout | Allow + warn | Block + error |
| HTTP 5xx | Allow + warn | Block + error |
| HTTP 401/403 | Always block (auth error) | Always block |
| HTTP 429 (rate limit) | Allow + warn | Block + error |
| JSON parse error | Allow + warn | Block + error |
| Invalid response | Allow + warn | Block + error |

---

## Further Reading

- [LangChain Middleware Deep Dive](./langchain_explained.md)
- [F5 AI Guardrails Documentation](https://www.f5.com/products/ai-guardrails)
- [Implementation Plan](../implementation_plan.md)
