# Implementation Plan

> **Status: ✅ COMPLETE (v0.2.0)** — All steps implemented, 68/68 tests passing, verified with real `create_agent()` on 2025-05-20.
>
> **Key post-plan discoveries**: Three additional requirements were discovered during integration testing that were not in the original plan:
> 1. Hook methods need `__can_jump_to__ = ["end"]` attribute for LangGraph conditional edge routing
> 2. Blocking must return `{"jump_to": "end"}` dict (not `Command` objects)
> 3. LangChain message objects use `.type` (`"human"`, `"ai"`) not `.role` (`"user"`, `"assistant"`)

[Overview]
Build `langchain-f5-aiguardrails`, a production-ready LangChain agent middleware that integrates F5 AI Guardrails for runtime security scanning of LLM prompts and responses.

This middleware enables LangChain users to add F5 AI Guardrails protection to any agent with a single line of configuration. It scans prompts before they reach the LLM and responses before they reach the user, using F5's out-of-band scan API (`POST /backend/v1/scans`). The middleware supports enforce mode (block violations), monitor mode (log only), and off mode (skip scanning). It is designed as an open-source PyPI package for F5 customers, following LangChain partner naming conventions.

The project targets Python 3.10+ and uses an async-first architecture with `httpx` for HTTP, `pydantic` for type validation, and LangChain's `AgentMiddleware` base class for the middleware hooks. The implementation prioritizes production readiness: fail-open/fail-closed behavior, proper connection lifecycle, comprehensive error handling, structured logging, and full test coverage.

[Types]
Pydantic models matching the F5 AI Guardrails API schema for type-safe request/response handling.

### `ScanRequest` (maps to PostScansBody)
```python
class ScanRequest(BaseModel):
    input: str                                          # Required — text to scan
    project: str | None = None                          # Project ID or friendly ID
    verbose: bool = False                               # Return detailed scanner results
    flag_only: bool = True                              # Flag vs block behavior (API field: flagOnly)
    disabled: list[str] = Field(default_factory=list)   # Disable scanners by type/ID
    force_enabled: list[str] = Field(default_factory=list)  # Force-enable scanners (API: forceEnabled)
    config_overrides: dict[str, Any] = Field(default_factory=dict)  # Per-scanner overrides (API: configOverrides)
    external_metadata: dict[str, str] | None = None     # Custom metadata, max 10 items (API: externalMetadata)
```

### `ScannerResult` (maps to Scan object in scannerResults)
```python
class ScannerResult(BaseModel):
    scanner_id: str                           # UUID of the scanner (API: scannerId)
    outcome: str                              # "passed" | "flagged" | "blocked" | "redacted"
    scan_direction: str                       # "request" | "response" (API: scanDirection)
    started_date: datetime | None = None      # API: startedDate
    completed_date: datetime | None = None    # API: completedDate
    data: dict[str, Any] | None = None        # Scanner-specific result data
    custom_config: bool = False               # API: customConfig
```

### `ScanResult` (maps to ScanRequestResult)
```python
class ScanResult(BaseModel):
    outcome: Literal["cleared", "flagged", "redacted", "blocked"]
    scanner_results: list[ScannerResult] = Field(default_factory=list, alias="scannerResults")
```

### `ScanResponse` (maps to PostScansResponse)
```python
class ScanResponse(BaseModel):
    id: str | None = None                   # Scan request ID (UUID)
    result: ScanResult                       # Contains outcome + scanner details
    redacted_input: str = ""                 # Input after redaction (API: redactedInput)
    scanners: dict[str, Any] | None = None   # Project scanners config if verbose

    @property
    def is_safe(self) -> bool:
        return self.result.outcome == "cleared"

    @property
    def outcome(self) -> str:
        return self.result.outcome
```

### `GuardrailConfig`
```python
class GuardrailConfig(BaseModel):
    api_key_request: str                         # F5 AI Guardrails API key for request scanning
    api_key_response: str                        # F5 AI Guardrails API key for response scanning
    base_url: str = "https://us1.calypsoai.app"  # Base URL for the API
    project: str | None = None                   # Default project for scans
    mode: Literal["enforce", "monitor", "off"] = "enforce"
    fail_open: bool = True                       # Allow on API errors
    timeout: int = 30                            # HTTP timeout in seconds
    verbose: bool = False                        # Request verbose scan results
    blocked_message: str = "This request has been blocked by F5 AI Guardrails security policy."
```

### `ScanDirection` (enum)
```python
class ScanDirection(str, Enum):
    PROMPT = "prompt"
    RESPONSE = "response"
```

[Files]
All source files for the package, tests, examples, and configuration.

### New Files to Create

**Package source (`src/langchain_f5_aiguardrails/`)**
- `__init__.py` — Public API exports: `F5GuardrailMiddleware`, `F5GuardrailClient`, `ScanRequest`, `ScanResponse`, `GuardrailConfig`
- `_version.py` — `__version__ = "0.1.0"`
- `types.py` — All Pydantic models listed in [Types] section
- `config.py` — `GuardrailConfig` class with `from_env()` class method
- `client.py` — `F5GuardrailClient` with sync/async scan methods
- `middleware.py` — `F5GuardrailMiddleware(AgentMiddleware)` class
- `exceptions.py` — `F5GuardrailError`, `F5GuardrailAPIError`, `F5GuardrailAuthError`, `F5GuardrailTimeoutError`

**Tests (`tests/`)**
- `__init__.py` — Empty
- `conftest.py` — Shared fixtures (mock client, respx setup, sample data)
- `test_types.py` — Pydantic model validation tests
- `test_client.py` — HTTP client tests with respx mocking
- `test_middleware.py` — Middleware logic tests (enforce/monitor/off, fail-open/closed)
- `test_config.py` — Configuration and env var tests
- `test_integration.py` — End-to-end middleware integration tests

**Examples (`examples/`)**
- `01_basic_enforce.py` — Block violations in enforce mode
- `02_monitor_mode.py` — Log-only mode with violation callback
- `03_custom_callback.py` — Custom violation handler for metrics/alerting
- `04_env_configuration.py` — Environment variable configuration
- `05_with_tools.py` — Agent with tools and guardrail middleware
- `06_manual_scan_test.py` — Direct API test script (no LangChain dependency)

**Project root**
- `pyproject.toml` — Package metadata, dependencies, build config
- `README.md` — User-facing documentation
- `CHANGELOG.md` — Version history
- `LICENSE` — MIT license text
- `.env.example` — Environment variable template

### Existing Files (No Modifications)
- `openapi.json` — F5 API spec (reference only)
- `.gitignore` — Already configured
- `claude.md` — AI assistant context (already created)
- `docs/langchain_explained.md` — LangChain documentation (already created)
- `docs/integration_strategies.md` — Integration strategies (already created)

[Functions]
All public and key internal functions for the package.

### `F5GuardrailClient` — `client.py`
- `__init__(self, api_key: str, base_url: str, project: str | None, timeout: int)` — Initialize client with config (single key per client instance)
- `scan(self, request: ScanRequest) -> ScanResponse` — Synchronous scan call
- `scan_async(self, request: ScanRequest) -> ScanResponse` — Async scan call
- `_build_payload(self, request: ScanRequest) -> dict` — Convert ScanRequest to API JSON payload
- `_parse_response(self, data: dict) -> ScanResponse` — Parse API JSON into ScanResponse
- `_handle_error(self, exc: Exception, fail_open: bool) -> ScanResponse | None` — Error handling with fail-open/closed
- `close(self)` — Close sync HTTP client
- `close_async(self)` — Close async HTTP client
- `from_env(cls) -> F5GuardrailClient` — Class method: create from environment variables

### `F5GuardrailMiddleware` — `middleware.py`
- `__init__(self, api_key_request: str, api_key_response: str, base_url: str, mode: str, fail_open: bool, timeout: int, project: str | None, verbose: bool, on_violation: Callable | None, blocked_message: str)` — Initialize middleware with separate API keys for request/response scanning
- `before_model(self, state: AgentState, runtime: Runtime) -> dict | None` — Scan prompt, block if violation in enforce mode
- `after_model(self, state: AgentState, runtime: Runtime) -> dict | None` — Scan response, block if violation in enforce mode
- `abefore_model(self, state: AgentState, runtime: Runtime) -> dict | None` — Async variant of before_model
- `aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None` — Async variant of after_model
- `_scan_content(self, content: str, direction: ScanDirection) -> ScanResponse | None` — Core sync scan logic with error handling
- `_scan_content_async(self, content: str, direction: ScanDirection) -> ScanResponse | None` — Core async scan logic
- `_handle_scan_result(self, result: ScanResponse, direction: ScanDirection) -> dict | None` — Decide block/allow/log based on mode
- `_extract_text(self, messages: list, direction: ScanDirection) -> str` — Extract text from message list
- `_build_blocked_response(self) -> dict` — Build the jump_to=end response dict
- `close(self)` — Close underlying client connections
- `from_env(cls) -> F5GuardrailMiddleware` — Class method: create from environment variables

### `GuardrailConfig` — `config.py`
- `from_env(cls) -> GuardrailConfig` — Load all config from F5_GUARDRAIL_* env vars
- `validate_mode(cls, v)` — Pydantic validator for mode field
- `validate_base_url(cls, v)` — Pydantic validator for base_url field

[Classes]
All classes for the package.

### New Classes

**`F5GuardrailMiddleware`** — `src/langchain_f5_aiguardrails/middleware.py`
- Inherits: `AgentMiddleware` (from `langchain.agents.middleware`)
- Key methods: `before_model`, `after_model`, `abefore_model`, `aafter_model`, `close`, `from_env`
- Holds: `F5GuardrailClient` instance, config, callbacks

**`F5GuardrailClient`** — `src/langchain_f5_aiguardrails/client.py`
- Inherits: none (standalone)
- Key methods: `scan`, `scan_async`, `close`, `close_async`, `from_env`
- Holds: `httpx.Client` (lazy), `httpx.AsyncClient` (lazy), config

**`GuardrailConfig`** — `src/langchain_f5_aiguardrails/config.py`
- Inherits: `pydantic.BaseModel`
- Key methods: `from_env`
- Fields: api_key_request, api_key_response, base_url, project, mode, fail_open, timeout, verbose, blocked_message

**`ScanRequest`** — `src/langchain_f5_aiguardrails/types.py`
- Inherits: `pydantic.BaseModel`
- Maps to: `PostScansBody` in openapi.json

**`ScanResponse`** — `src/langchain_f5_aiguardrails/types.py`
- Inherits: `pydantic.BaseModel`
- Maps to: `PostScansResponse` in openapi.json
- Properties: `is_safe`, `outcome`

**`ScanResult`** — `src/langchain_f5_aiguardrails/types.py`
- Inherits: `pydantic.BaseModel`
- Maps to: `ScanRequestResult` in openapi.json

**`ScannerResult`** — `src/langchain_f5_aiguardrails/types.py`
- Inherits: `pydantic.BaseModel`
- Maps to: `Scan` in openapi.json

**Exception classes** — `src/langchain_f5_aiguardrails/exceptions.py`
- `F5GuardrailError(Exception)` — base exception
- `F5GuardrailAPIError(F5GuardrailError)` — HTTP errors from the API
- `F5GuardrailAuthError(F5GuardrailError)` — authentication failures (401/403)
- `F5GuardrailTimeoutError(F5GuardrailError)` — request timeouts

[Dependencies]
Runtime and development dependencies for the package.

### Runtime Dependencies (`pyproject.toml`)
```toml
[project]
dependencies = [
    "langchain-core>=0.3",
    "langgraph>=0.4",
    "httpx>=0.27",
    "pydantic>=2.0",
]
```

### Development Dependencies
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
    "ruff>=0.8",
    "mypy>=1.13",
]
examples = [
    "langchain-openai>=0.3",
    "python-dotenv>=1.0",
]
```

[Testing]
Comprehensive test suite using pytest with async support and HTTP mocking.

### Test Framework
- **pytest** with `pytest-asyncio` for async tests
- **respx** for httpx HTTP mocking (no monkey-patching)
- Fixtures in `conftest.py` for shared setup

### `tests/conftest.py` — Shared Fixtures
- `api_base_url` — returns `"https://us1.calypsoai.app"`
- `MOCK_API_KEY` — `"test-api-key-12345"` (for single-client tests)
- `MOCK_API_KEY_REQUEST` — `"test-request-api-key"` (for middleware request scanning)
- `MOCK_API_KEY_RESPONSE` — `"test-response-api-key"` (for middleware response scanning)
- `cleared_response_json` — JSON for a cleared scan response
- `blocked_response_json` — JSON for a blocked scan response
- `flagged_response_json` — JSON for a flagged scan response
- `guardrail_client()` — configured F5GuardrailClient (single key)
- `middleware_enforce()` — middleware in enforce mode (dual keys: request + response)
- `middleware_monitor()` — middleware in monitor mode (dual keys: request + response)

### `tests/test_types.py` — Model Validation
- `test_scan_request_minimal` — only `input` field required
- `test_scan_request_full` — all fields populated
- `test_scan_request_metadata_limit` — max 10 external_metadata items
- `test_scan_response_is_safe_cleared` — is_safe=True when cleared
- `test_scan_response_is_safe_blocked` — is_safe=False when blocked
- `test_scan_response_outcome_property` — outcome accessor works
- `test_scanner_result_parsing` — parse scanner result JSON
- `test_guardrail_config_defaults` — default values correct
- `test_guardrail_config_from_env` — env var loading

### `tests/test_client.py` — HTTP Client
- `test_scan_cleared` — cleared response parsed correctly
- `test_scan_blocked` — blocked response parsed correctly
- `test_scan_flagged` — flagged response parsed correctly
- `test_scan_redacted` — redacted response and redactedInput
- `test_scan_with_project` — project parameter included in payload
- `test_scan_with_metadata` — externalMetadata serialized correctly
- `test_scan_auth_header` — Bearer token sent in Authorization header
- `test_scan_timeout_fail_open` — timeout returns None when fail_open=True
- `test_scan_timeout_fail_closed` — timeout raises when fail_open=False
- `test_scan_server_error_fail_open` — 500 returns None when fail_open
- `test_scan_auth_error` — 401/403 always raises F5GuardrailAuthError
- `test_scan_async_cleared` — async variant works
- `test_client_close` — client closes HTTP connections

### `tests/test_middleware.py` — Middleware Logic
- `test_before_model_cleared` — returns None on cleared scan
- `test_before_model_blocked_enforce` — returns jump_to=end on blocked
- `test_before_model_blocked_monitor` — returns None (never blocks in monitor)
- `test_before_model_mode_off` — skips scanning entirely
- `test_after_model_cleared` — returns None on cleared response
- `test_after_model_blocked_enforce` — blocks response in enforce mode
- `test_after_model_blocked_monitor` — logs but doesn't block
- `test_violation_callback_called` — on_violation invoked on violation
- `test_violation_callback_not_called_on_clear` — not invoked when cleared
- `test_fail_open_on_timeout` — returns None on API timeout
- `test_fail_closed_on_timeout` — blocks on API timeout
- `test_blocked_message_customizable` — custom blocked_message used
- `test_from_env` — middleware created from environment variables

### `tests/test_integration.py` — End-to-End
- `test_full_flow_cleared` — prompt cleared, LLM called, response cleared
- `test_full_flow_prompt_blocked` — prompt blocked, LLM never called
- `test_full_flow_response_blocked` — LLM called, response blocked
- `test_monitor_mode_full_flow` — violations logged but never blocked

### Example Files as Manual Tests

**`examples/06_manual_scan_test.py`** — Direct API validation script:
- Creates F5GuardrailClient directly
- Sends benign text → expects "cleared"
- Sends suspicious text → expects "flagged" or "blocked"
- Tests timeout handling
- Tests auth error handling
- Prints results in human-readable format
- Can be run with: `python examples/06_manual_scan_test.py`

[Implementation Order]
Numbered steps for the implementation sequence to minimize conflicts and ensure each step builds on the previous.

1. **Project scaffolding** — Create `pyproject.toml`, `LICENSE`, `.env.example`, package directory structure, empty `__init__.py` files
2. **Types and exceptions** — Implement `types.py` (Pydantic models) and `exceptions.py` (custom exceptions). These have no dependencies on other project files.
3. **Configuration** — Implement `config.py` with `GuardrailConfig` and `from_env()`. Depends on types.
4. **HTTP client** — Implement `client.py` with `F5GuardrailClient`. Depends on types, config, exceptions.
5. **Test fixtures** — Create `tests/conftest.py` with shared fixtures and sample data.
6. **Client tests** — Implement `tests/test_types.py` and `tests/test_client.py`. Validate all API interactions.
7. **Middleware** — Implement `middleware.py` with `F5GuardrailMiddleware`. Depends on client, types, config.
8. **Middleware tests** — Implement `tests/test_middleware.py` and `tests/test_config.py`.
9. **Integration tests** — Implement `tests/test_integration.py` for end-to-end flows.
10. **Package exports** — Wire up `__init__.py` with all public exports.
11. **Examples** — Create all example files (01-06).
12. **README and CHANGELOG** — Write user-facing documentation.
13. **Final review** — Run full test suite, linting, type checking. Verify all examples work.
