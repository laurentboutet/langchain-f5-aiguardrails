# Implementation Plan — Inline Proxy Mode (v0.3.0)

> Technical specification for the F5 AI Guardrails inline proxy integration with LangChain.
>
> **Status:** ✅ COMPLETE — All items implemented and tested (94/94 tests passing)

---

## Executive Summary

The inline proxy mode routes LLM traffic through the F5 AI Guardrails (CalypsoAI) proxy endpoint instead of making separate scan API calls. This enables:

1. **Single HTTP hop** — prompts and responses are scanned inline during the proxy pass
2. **Agentic Fingerprints** — CalypsoAI swimlane view that groups all LLM calls from the same workflow via a shared session ID
3. **Drop-in replacement** — `ChatF5OpenAI` is a genuine `ChatOpenAI` instance; all existing LangChain code works unchanged

---

## ✅ Phase 1: Research & Design

### 1.1 CalypsoAI Inline Proxy Architecture

- [x] **Understand the endpoint structure**
  - OpenAI proxy: `{base_url}/openai/{provider}/chat/completions`
  - Same auth token as scan API: `Authorization: Bearer {api_key}`
  - OpenAI-compatible request/response protocol

- [x] **Session tracking mechanism**
  - Header: `x-cai-metadata-session-id`
  - All requests with the same session ID appear in one CalypsoAI swimlane
  - Enables "Agentic Fingerprints" feature — visibility into multi-agent workflows

- [x] **Design decision: Wrapper vs Subclass**
  - Option A: Subclass `ChatOpenAI` → complex, breaks with langchain-openai updates
  - Option B: Wrapper class → extra layer, `isinstance` checks fail
  - **Option C (chosen):** Factory using `__new__` → returns genuine `ChatOpenAI`, passes all `isinstance` checks

### 1.2 LangChain Integration Points

- [x] **`ChatOpenAI` accepts `base_url` kwarg**
  - Sets the OpenAI-compatible API endpoint
  - Can point to any proxy that implements OpenAI protocol

- [x] **`default_headers` kwarg**
  - Injects custom headers on every HTTP request
  - Used to inject `x-cai-metadata-session-id`

- [x] **`langchain-openai` is optional**
  - Package should work in middleware-only mode without `langchain-openai`
  - Import check at runtime with clear error message

---

## ✅ Phase 2: Implementation

### 2.1 F5SessionManager Class

**File:** `src/langchain_f5_aiguardrails/session.py`

- [x] **Core design**
  ```python
  class F5SessionManager:
      def __init__(self, *, prefix: str = "workflow", session_id: str | None = None):
          self._session_id = session_id or f"{prefix}-{uuid.uuid4()}"
      
      @property
      def session_id(self) -> str:
          return self._session_id
      
      @property
      def headers(self) -> dict[str, str]:
          return {SESSION_HEADER: self._session_id}
  ```

- [x] **Session ID generation**
  - Default: `{prefix}-{uuid4}` (e.g., `workflow-550e8400-e29b-41d4-a716-446655440000`)
  - Explicit: user can pass `session_id="custom-id"` to override
  - URL-safe characters only (alphanumeric + hyphen + underscore)

- [x] **Header constant**
  - `SESSION_HEADER = "x-cai-metadata-session-id"`
  - Exported from module for testing/inspection

- [x] **Immutability**
  - Session ID set once at construction
  - Repeated `.session_id` calls return same value

### 2.2 ChatF5OpenAI Factory Class

**File:** `src/langchain_f5_aiguardrails/chat_models.py`

- [x] **`__new__` pattern**
  ```python
  class ChatF5OpenAI:
      def __new__(
          cls,
          *,
          f5_provider: str | None = None,
          f5_base_url: str | None = None,
          f5_api_key: str | None = None,
          session_manager: F5SessionManager | None = None,
          **kwargs: Any,
      ) -> Any:
          # Returns a ChatOpenAI instance, NOT a ChatF5OpenAI instance
          return _ChatOpenAIBase(base_url=..., api_key=..., default_headers=..., **kwargs)
  ```

- [x] **Why `__new__` instead of `__init__`**
  - Allows returning a different class instance
  - `isinstance(ChatF5OpenAI(...), ChatOpenAI)` → `True`
  - Works seamlessly with all LangChain APIs that type-check for `BaseChatModel`

- [x] **Proxy URL construction**
  ```python
  def _build_openai_proxy_url(base_url: str, provider: str) -> str:
      return f"{base_url.rstrip('/')}/openai/{provider.strip('/')}"
  ```
  - Handles trailing slashes on base_url
  - Handles leading/trailing slashes on provider name

- [x] **Environment variable resolution**
  | Parameter | Env var | Default |
  |-----------|---------|---------|
  | `f5_api_key` | `F5_GUARDRAIL_API_KEY` | *(required)* |
  | `f5_base_url` | `F5_GUARDRAIL_BASE_URL` | `https://us1.calypsoai.app` |
  | `f5_provider` | `F5_GUARDRAIL_PROVIDER_OPENAI` | *(required)* |

- [x] **Session header injection**
  ```python
  default_headers = kwargs.pop("default_headers", {})
  if session_manager:
      default_headers.update(session_manager.headers)
  ```

- [x] **`from_env()` factory method**
  ```python
  @classmethod
  def from_env(cls, **kwargs) -> Any:
      return cls(**kwargs)  # All params read from env if not provided
  ```

- [x] **Import guard**
  ```python
  try:
      from langchain_openai import ChatOpenAI as _ChatOpenAIBase
  except ImportError:
      _ChatOpenAIBase = None
  
  # In __new__:
  if _ChatOpenAIBase is None:
      raise ImportError("langchain-openai is required for ChatF5OpenAI...")
  ```

### 2.3 Package Exports

**File:** `src/langchain_f5_aiguardrails/__init__.py`

- [x] **New exports added**
  ```python
  from .chat_models import ChatF5OpenAI
  from .session import F5SessionManager
  
  __all__ = [
      # ... existing exports ...
      "ChatF5OpenAI",
      "F5SessionManager",
  ]
  ```

- [x] **Module docstring updated**
  - Quick start examples for both modes

### 2.4 Dependencies

**File:** `pyproject.toml`

- [x] **New optional dependency group**
  ```toml
  [project.optional-dependencies]
  openai = ["langchain-openai>=0.3"]
  ```

- [x] **Added to `[dev]` for testing**
  ```toml
  dev = [
      # ... existing deps ...
      "langchain-openai>=0.3",
  ]
  ```

---

## ✅ Phase 3: Testing

### 3.1 F5SessionManager Tests

**File:** `tests/test_session.py` (10 tests)

- [x] `test_auto_generate_session_id_with_default_prefix`
- [x] `test_auto_generate_session_id_with_custom_prefix`
- [x] `test_explicit_session_id_is_used`
- [x] `test_explicit_session_id_ignores_prefix`
- [x] `test_headers_property`
- [x] `test_headers_uses_correct_header_name`
- [x] `test_session_id_is_immutable`
- [x] `test_different_instances_have_different_ids`
- [x] `test_repr`
- [x] `test_session_id_format_is_url_safe`

### 3.2 ChatF5OpenAI Tests

**File:** `tests/test_chat_models.py` (16 tests)

**URL Building Tests (4):**
- [x] `test_basic_url_building`
- [x] `test_strips_trailing_slash_from_base_url`
- [x] `test_strips_slashes_from_provider`
- [x] `test_multiple_trailing_slashes`

**ChatF5OpenAI Tests (12):**
- [x] `test_raises_import_error_when_langchain_openai_not_installed`
- [x] `test_raises_value_error_when_api_key_missing`
- [x] `test_raises_value_error_when_provider_missing`
- [x] `test_creates_chat_openai_with_correct_base_url`
- [x] `test_creates_chat_openai_with_api_key`
- [x] `test_injects_session_headers_when_session_manager_provided`
- [x] `test_no_session_header_when_session_manager_not_provided`
- [x] `test_passes_through_model_kwargs`
- [x] `test_explicit_params_override_env_vars`
- [x] `test_merges_user_provided_default_headers`
- [x] `test_from_env_factory_method`
- [x] `test_returns_chat_openai_instance`

### 3.3 Test Results

```
================================= test session starts ==================================
collected 94 items
...
============================= 94 passed in 13.79s ======================================
```

---

## ✅ Phase 4: Documentation & Examples

### 4.1 Example Script

**File:** `examples/07_inline_openai.py`

- [x] **Complete working example**
  - Creates `F5SessionManager` with prefix
  - Creates `ChatF5OpenAI.from_env()` with session manager
  - Single invoke example
  - Multi-turn conversation example
  - Prints session ID for dashboard lookup

### 4.2 Documentation Updates

- [x] **`README.md`** — Both modes documented, inline proxy is "Mode 1"
- [x] **`examples/README.md`** — Example 07 added with setup instructions
- [x] **`.env.example`** — Inline proxy section added
- [x] **`CHANGELOG.md`** — v0.3.0 release notes
- [x] **`TASK_HANDOFF.md`** — Updated to v0.3.0
- [x] **`claude.md`** — Updated to v0.3.0

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           User Application                                   │
│                                                                             │
│   session = F5SessionManager(prefix="order-workflow")                       │
│   llm = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o")     │
│   response = llm.invoke("Process order #12345")                             │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP POST
                                    │ Authorization: Bearer {api_key}
                                    │ x-cai-metadata-session-id: order-workflow-550e8400-...
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                      F5 AI Guardrails Proxy (CalypsoAI)                      │
│                                                                               │
│   1. Receive request at /openai/{provider}/chat/completions                  │
│   2. Scan prompt (inline) — detect injection, PII, policy violations         │
│   3. If blocked → return error response                                       │
│   4. If safe → forward to real LLM (OpenAI, Azure, etc.)                     │
│   5. Receive LLM response                                                     │
│   6. Scan response (inline) — detect leakage, harmful content                │
│   7. If blocked → return sanitized/error response                            │
│   8. If safe → return to caller                                              │
│   9. Log to Agentic Fingerprint swimlane (grouped by session ID)            │
└───────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                              Real LLM API                                     │
│                        (OpenAI, Azure OpenAI, etc.)                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Code Snippets

### F5SessionManager Usage

```python
from langchain_f5_aiguardrails import F5SessionManager

# Auto-generated UUID with prefix
session = F5SessionManager(prefix="k8s-debug")
print(session.session_id)  # "k8s-debug-550e8400-e29b-41d4-..."

# Explicit session ID (e.g., from incoming request)
session = F5SessionManager(session_id=request.headers["x-request-id"])

# Get headers dict for manual use
print(session.headers)  # {"x-cai-metadata-session-id": "..."}
```

### ChatF5OpenAI Usage

```python
from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager

# Method 1: from_env() — reads all from environment
session = F5SessionManager(prefix="my-agent")
llm = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o-mini")

# Method 2: explicit parameters
llm = ChatF5OpenAI(
    f5_api_key="cai_xxxx",
    f5_base_url="https://us1.calypsoai.app",
    f5_provider="my-openai-provider",
    session_manager=session,
    model="gpt-4o",
    temperature=0.7,
)

# Use like any ChatOpenAI
response = llm.invoke("Hello!")
print(response.content)

# Works with LangChain Expression Language (LCEL)
chain = prompt_template | llm | output_parser
result = chain.invoke({"topic": "AI security"})
```

### Multi-Agent Session Sharing

```python
from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager

# One session for the entire workflow
session = F5SessionManager(prefix="order-processing")

# Multiple agents share the same session
planner = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o")
executor = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o-mini")
validator = ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o-mini")

# All calls from planner, executor, and validator
# appear in ONE CalypsoAI swimlane, grouped by session ID
```

---

## Environment Variables Reference

| Variable | Mode | Required | Default | Description |
|----------|------|:--------:|---------|-------------|
| `F5_GUARDRAIL_API_KEY` | Both | ✅ | — | CalypsoAI API key |
| `F5_GUARDRAIL_BASE_URL` | Both | ❌ | `https://us1.calypsoai.app` | API base URL |
| `F5_GUARDRAIL_PROVIDER_OPENAI` | Inline | ✅* | — | Provider name for proxy route |

*Required when using `ChatF5OpenAI`

---

## Files Created/Modified in v0.3.0

| File | Action | Lines |
|------|--------|-------|
| `src/langchain_f5_aiguardrails/session.py` | Created | 54 |
| `src/langchain_f5_aiguardrails/chat_models.py` | Created | 176 |
| `src/langchain_f5_aiguardrails/__init__.py` | Modified | +12 |
| `src/langchain_f5_aiguardrails/_version.py` | Modified | 0.2.0 → 0.3.0 |
| `pyproject.toml` | Modified | +4 |
| `tests/test_session.py` | Created | 69 |
| `tests/test_chat_models.py` | Created | 216 |
| `examples/07_inline_openai.py` | Created | 66 |
| `README.md` | Modified | Rewritten |
| `examples/README.md` | Modified | +50 |
| `.env.example` | Modified | +30 |
| `CHANGELOG.md` | Modified | +25 |
| `TASK_HANDOFF.md` | Modified | Rewritten |
| `claude.md` | Modified | Rewritten |
| `implementation_plan_inline.md` | Created | This file |

---

## Conclusion

The inline proxy mode implementation is **complete**. All planned features were implemented:

1. ✅ `F5SessionManager` — lightweight session tracking for Agentic Fingerprints
2. ✅ `ChatF5OpenAI` — drop-in `ChatOpenAI` replacement via `__new__` pattern
3. ✅ Environment variable configuration
4. ✅ 26 new tests (10 + 16), 94/94 total passing
5. ✅ Example script with multi-turn conversation demo
6. ✅ Full documentation across README, examples, and handoff files

The package now supports two production modes:
- **Inline proxy** (`ChatF5OpenAI`) — recommended for production, enables Agentic Fingerprints
- **Middleware** (`F5GuardrailMiddleware`) — flexible, works with any LLM provider
