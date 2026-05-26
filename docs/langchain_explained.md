# LangChain & LangGraph Middleware — Complete Guide

> A comprehensive explanation of LangChain, LangGraph, and the middleware system for AI agent development.

---

## Table of Contents

1. [What is LangChain?](#1-what-is-langchain)
2. [What is LangGraph?](#2-what-is-langgraph)
3. [Agents: The Core Concept](#3-agents-the-core-concept)
4. [The Middleware System](#4-the-middleware-system)
5. [Node-Style Hooks In Depth](#5-node-style-hooks-in-depth)
6. [Wrap-Style Hooks In Depth](#6-wrap-style-hooks-in-depth)
7. [Class-Based Middleware](#7-class-based-middleware)
8. [State Management](#8-state-management)
9. [How It All Fits Together](#9-how-it-all-fits-together)
10. [Middleware for External Guardrails](#10-middleware-for-external-guardrails)

---

## 1. What is LangChain?

LangChain is a Python (and JavaScript) framework for building applications powered by large language models (LLMs). It provides:

- **Model abstractions** — unified interface across providers (OpenAI, Anthropic, Google, local models, etc.)
- **Tool integrations** — let LLMs call functions, APIs, databases
- **Memory and state** — manage conversation history and context
- **Chains and pipelines** — compose multiple steps into workflows
- **Agent architectures** — autonomous systems that reason and act

LangChain is not just for chatbots. It enables complex AI applications: autonomous agents, RAG (retrieval-augmented generation) systems, multi-agent workflows, and production-grade AI services.

### Key Packages

| Package | Purpose |
|---------|---------|
| `langchain-core` | Base abstractions (messages, runnables, prompts) |
| `langchain` | Higher-level agent and chain APIs |
| `langgraph` | Low-level graph-based agent orchestration |
| `langchain-openai` | OpenAI provider integration |
| `langchain-anthropic` | Anthropic provider integration |

---

## 2. What is LangGraph?

LangGraph is a **low-level orchestration framework** built on top of LangChain. While LangChain provides high-level abstractions, LangGraph gives you fine-grained control over:

- **State machines** — define agent behavior as graphs of nodes and edges
- **Durable execution** — persist state across runs
- **Human-in-the-loop** — pause execution for approval
- **Streaming** — real-time output as the agent works
- **Middleware** — inject logic at every step of the agent loop

### The Agent Loop

An LLM agent runs in a loop:

```
1. Read current state (conversation history, context)
2. Call the LLM to decide what to do next
3. If the LLM wants to use a tool → execute the tool
4. Update state with the result
5. Repeat until the LLM produces a final answer (or iteration limit)
```

LangGraph models this loop as a **directed graph**:

```
      ┌──────────┐
      │  input   │
      └────┬─────┘
           │
           ▼
      ┌──────────┐
      │  model   │◄──────────┐
      └────┬─────┘           │
           │                 │
           ▼                 │
      ┌──────────┐     ┌─────┴────┐
      │ decision │────►│  tools   │
      └────┬─────┘     └──────────┘
           │
           ▼
      ┌──────────┐
      │  output  │
      └──────────┘
```

---

## 3. Agents: The Core Concept

### `create_agent` — The High-Level Factory

`create_agent` builds a production-ready LangGraph agent with a single function call:

```python
from langchain.agents import create_agent

agent = create_agent(
    model="openai:gpt-4.1",    # LLM provider and model
    tools=[search, calculator],  # Tools the agent can use
    middleware=[...],            # Middleware hooks (our entry point)
    state_schema=CustomState,   # Optional custom state class
)

result = agent.invoke({"messages": [{"role": "user", "content": "Hello!"}]})
```

Under the hood, `create_agent` builds a LangGraph state machine with:
- A **model node** that calls the LLM
- A **tools node** that executes tool calls
- **Conditional edges** that route between them
- **Middleware nodes** inserted at the right places

### Agent State

The agent maintains a **state** object that flows through the graph. At minimum it contains `messages` (the conversation history), but you can extend it:

```python
from langchain.agents.middleware import AgentState

class CustomState(AgentState):
    user_id: str | None = None
    session_id: str | None = None
    scan_results: dict | None = None
```

---

## 4. The Middleware System

Middleware provides **hook points** into the agent loop. There are two categories:

### Node-Style Hooks

These become separate nodes in the LangGraph graph. They run at specific points and can read/modify agent state or short-circuit execution.

| Hook | When it runs | Use case |
|------|-------------|----------|
| `before_agent` | Once, at the start of agent invocation | Authentication, setup |
| `before_model` | Before **each** LLM call | Input validation, guardrails |
| `after_model` | After **each** LLM response | Output filtering, guardrails |
| `after_agent` | Once, when the agent finishes | Cleanup, metrics |

**Signature:**
```python
def hook(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    # Return None → no changes, continue normally
    # Return dict → update state, optionally jump to "end"
    pass
```

### Wrap-Style Hooks

These wrap the actual LLM or tool call. They don't appear as separate nodes — they wrap the function itself.

| Hook | What it wraps | Use case |
|------|--------------|----------|
| `wrap_model_call` | Each LLM invocation | Retry logic, model routing |
| `wrap_tool_call` | Each tool execution | Tool-level security, auditing |

**Signature:**
```python
def hook(request: RequestType, handler: Callable) -> ResponseType:
    # Pre-processing
    response = handler(request)  # Call the actual LLM/tool
    # Post-processing
    return response
```

### Execution Flow with Middleware

```
before_agent
    │
    ▼
before_model  ──► wrap_model_call ──► LLM ──► after_model
    │                                              │
    │              ┌───────────────────────────────┘
    │              │ (if tool calls requested)
    │              ▼
    │         wrap_tool_call ──► Tool execution
    │              │
    │              ▼
    │         before_model (next iteration) ──► ...
    │
    ▼
after_agent
```

---

## 5. Node-Style Hooks In Depth

### `before_model` — Pre-LLM Logic

This is the primary hook for **input guardrails**. It runs before every LLM call in the agent loop.

```python
from langchain.agents.middleware import before_model, AgentState
from typing import Any

@before_model(can_jump_to=["end"])
def scan_prompt(state: AgentState, runtime) -> dict[str, Any] | None:
    last_message = state["messages"][-1]
    
    # Call external guardrail API
    scan_result = guardrail_api.scan(last_message.content)
    
    if scan_result.outcome == "blocked":
        # Short-circuit: return a blocked message and end the agent
        return {
            "messages": [AIMessage("I cannot process this request due to policy restrictions.")],
            "jump_to": "end",
        }
    
    return None  # Content is safe, continue to LLM
```

**Key points:**
- `can_jump_to=["end"]` tells LangGraph this hook may redirect to the end node
- The returned dict is **merged** into agent state
- `"jump_to": "end"` stops the agent loop immediately

### `after_model` — Post-LLM Logic

This is the primary hook for **output guardrails**. It runs after every LLM response.

```python
from langchain.agents.middleware import after_model
from langchain.messages import AIMessage

@after_model(can_jump_to=["end"])
def scan_response(state: AgentState, runtime) -> dict[str, Any] | None:
    last_message = state["messages"][-1]
    
    if isinstance(last_message, AIMessage):
        scan_result = guardrail_api.scan(last_message.content)
        
        if scan_result.outcome == "blocked":
            # Replace the response with a safe message
            return {
                "messages": [AIMessage("The generated response was blocked by security policy.")],
                "jump_to": "end",
            }
    
    return None  # Response is safe
```

### `before_agent` / `after_agent`

These run once per agent invocation (not per loop iteration):

```python
from langchain.agents.middleware import before_agent, after_agent

@before_agent
def setup(state: AgentState, runtime) -> dict[str, Any] | None:
    print(f"Agent invocation started with {len(state['messages'])} messages")
    return None

@after_agent
def teardown(state: AgentState, runtime) -> dict[str, Any] | None:
    print(f"Agent finished with {len(state['messages'])} messages")
    return None
```

---

## 6. Wrap-Style Hooks In Depth

### `wrap_model_call`

Wraps the actual LLM invocation. Useful for retry logic, model switching, and request modification.

```python
from langchain.agents.middleware import wrap_model_call

@wrap_model_call
def retry_on_failure(request, handler):
    for attempt in range(3):
        try:
            return handler(request)
        except Exception as e:
            if attempt == 2:
                raise
            print(f"Retry {attempt + 1}/3: {e}")
```

The `request` object provides access to:
- `request.state` — current agent state
- `request.runtime` — runtime context
- `request.messages` — model input
- `request.tools` — active tools
- `request.override(...)` — create a modified request

### `wrap_tool_call`

Wraps each tool execution. Critical for tool-level security.

```python
from langchain.agents.middleware import wrap_tool_call
from langchain.tools.tool_node import ToolCallRequest
from langchain.messages import ToolMessage
from langgraph.types import Command

@wrap_tool_call
def audit_tool_calls(request: ToolCallRequest, handler) -> ToolMessage | Command:
    tool_name = request.tool_call["name"]
    tool_args = request.tool_call["args"]
    
    print(f"Tool call: {tool_name}({tool_args})")
    
    result = handler(request)  # Execute the tool
    
    print(f"Tool result: {result}")
    
    return result
```

**Important:** To update persistent agent state from `wrap_tool_call`, you must use `Command(update=...)` — not direct state mutation.

---

## 7. Class-Based Middleware

For production use, the class-based approach is recommended. It groups related hooks into a single, configurable object:

```python
from langchain.agents.middleware import AgentMiddleware, AgentState
from typing import Any

class SecurityMiddleware(AgentMiddleware):
    """Middleware that scans prompts and responses for security violations."""
    
    def __init__(self, api_key: str, mode: str = "enforce"):
        self.api_key = api_key
        self.mode = mode
    
    def before_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        """Scan the prompt before sending to the LLM."""
        # ... scan logic ...
        return None
    
    def after_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        """Scan the response before returning to the user."""
        # ... scan logic ...
        return None
    
    # Async variants for async agent pipelines
    async def abefore_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        return None
    
    async def aafter_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        return None
```

Usage:

```python
from langchain.agents import create_agent

agent = create_agent(
    model="openai:gpt-4.1",
    tools=[...],
    middleware=[SecurityMiddleware(api_key_request="...", api_key_response="...", mode="enforce")],
)
```

### Composing Multiple Middleware

Multiple middleware are applied in order:

```python
agent = create_agent(
    model="openai:gpt-4.1",
    tools=[...],
    middleware=[
        LoggingMiddleware(),           # Logs all requests
        SecurityMiddleware(...),        # Scans for security violations
        RateLimitMiddleware(max=100),   # Limits request rate
    ],
)
```

Each middleware's hooks run in sequence. If any `before_model` returns `{"jump_to": "end"}`, subsequent middleware and the LLM call are skipped.

---

## 8. State Management

### Reading State

All hooks receive the current agent state. For `before_model` / `after_model`, this includes:
- `state["messages"]` — full conversation history
- Custom fields if using a custom `state_schema`

### Updating State

**From node-style hooks:** Return a dict of updates.

```python
@before_model
def add_metadata(state, runtime):
    return {"scan_count": state.get("scan_count", 0) + 1}
```

**From `wrap_tool_call`:** Use `Command(update=...)`.

```python
@wrap_tool_call
def track_tools(request, handler):
    result = handler(request)
    
    if isinstance(result, ToolMessage):
        return Command(update={
            "messages": [result],
            "tools_used": [request.tool_call["name"]],
        })
    
    return result
```

### Short-Circuiting (Blocking)

To stop the agent immediately:

```python
return {
    "messages": [AIMessage("Blocked by policy.")],
    "jump_to": "end",
}
```

This is how guardrail middleware enforces security — by jumping to the end node when a violation is detected.

---

## 9. How It All Fits Together

Here's the complete picture of a LangChain agent with guardrail middleware:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import AIMessage
from typing import Any

class F5GuardrailMiddleware(AgentMiddleware):
    def __init__(self, api_key, base_url, mode="enforce"):
        self.client = F5GuardrailClient(api_key, base_url)
        self.mode = mode
    
    def before_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        # Extract the latest user message
        messages = state["messages"]
        prompt_text = messages[-1].content if messages else ""
        
        # Scan the prompt
        result = self.client.scan(prompt_text)
        
        if result.outcome in ("blocked", "flagged") and self.mode == "enforce":
            return {
                "messages": [AIMessage("This request was blocked by F5 AI Guardrails.")],
                "jump_to": "end",
            }
        
        return None  # Safe — proceed to LLM
    
    def after_model(self, state: AgentState, runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        response_text = messages[-1].content if messages else ""
        
        result = self.client.scan(response_text)
        
        if result.outcome in ("blocked", "flagged") and self.mode == "enforce":
            return {
                "messages": [AIMessage("The response was blocked by F5 AI Guardrails.")],
                "jump_to": "end",
            }
        
        return None

# Create the agent with guardrail middleware
agent = create_agent(
    model="openai:gpt-4.1",
    tools=[search_tool, calculator_tool],
    middleware=[
        F5GuardrailMiddleware(
            api_key_request="your-request-api-key",
            api_key_response="your-response-api-key",
            base_url="https://us1.calypsoai.app",
            mode="enforce",
        ),
    ],
)

# Use the agent
result = agent.invoke({
    "messages": [{"role": "user", "content": "What is the weather today?"}]
})
```

---

## 10. Middleware for External Guardrails

When integrating an external guardrail service (like F5 AI Guardrails) into LangChain, middleware is the ideal pattern because:

1. **Transparent** — the agent code doesn't change. Tools and prompts remain untouched.
2. **Composable** — add/remove the guardrail by adding/removing the middleware.
3. **Centralized** — all security logic lives in one place.
4. **Testable** — mock the guardrail API to test middleware behavior independently.
5. **Production-ready** — fail-open/fail-closed behavior, logging, metrics.

### The Out-of-Band Pattern

The middleware calls the guardrail API **out of band** — separately from the LLM call:

```
Client → [before_model: scan prompt] → LLM → [after_model: scan response] → Client
                    │                                       │
                    ▼                                       ▼
           F5 AI Guardrails API                   F5 AI Guardrails API
           (POST /backend/v1/scans)               (POST /backend/v1/scans)
```

This pattern means:
- The LLM provider never sees the guardrail — it's invisible to them
- The guardrail is model-agnostic — works with any LLM provider
- You can switch between enforce/monitor without changing anything else
- The middleware handles all error cases (API timeout, network errors, etc.)

---

## Further Reading

- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Agents Overview](https://langchain-ai.github.io/langgraph/agents/overview/)
- [F5 AI Guardrails](https://www.f5.com/products/ai-guardrails)
