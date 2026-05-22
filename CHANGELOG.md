# Changelog

All notable changes to `langchain-f5-aiguardrails` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-05-21

### Added
- **Inline proxy mode** — New `ChatF5OpenAI` class that routes LLM traffic through the F5 AI Guardrails proxy (`/openai/{provider}/chat/completions`) instead of making separate scan API calls. This enables:
  - **Agentic Fingerprints** — CalypsoAI swimlane view of all agent calls in a workflow
  - **Session tracking** via `x-cai-metadata-session-id` header
  - Inline scanning of both prompts and responses in a single HTTP hop
  - Full compatibility with tool calls and multi-turn conversations
- **`F5SessionManager`** — Lightweight session ID manager for the `x-cai-metadata-session-id` header. Auto-generates UUID-based session IDs with a configurable prefix, or accepts user-provided IDs. Multiple agents sharing the same session manager appear in a single CalypsoAI swimlane.
- **`ChatF5OpenAI`** — Drop-in replacement for `ChatOpenAI` that automatically configures `base_url` to point to the F5 proxy and injects session headers on every request. Supports `from_env()` factory for environment-variable-based configuration.
- New environment variables for inline proxy mode:
  - `F5_GUARDRAIL_PROVIDER_OPENAI` — F5 provider name for OpenAI-compatible models
- New optional dependency group `[openai]` for `langchain-openai>=0.3`
- 26 new tests (10 for `F5SessionManager`, 16 for `ChatF5OpenAI`) — total now 94/94 passing
- Example script `examples/07_inline_openai.py`

### Changed
- Updated package description to reflect both middleware and inline proxy modes
- `langchain-openai` added to `[dev]` dependencies for testing

## [0.2.0] - 2025-05-20

### Fixed
- **`create_agent()` integration** — Middleware hooks (`before_model`, `after_model`) now correctly fire when used with LangChain's `create_agent()` factory. Three root causes were identified and fixed:
  1. Added `__can_jump_to__ = ["end"]` attribute on all hook methods. Without this, `create_agent()` wired only plain edges in the LangGraph (no conditional routing), so `jump_to: "end"` was silently ignored.
  2. Changed blocking return type from `Command(goto="__end__")` to `{"jump_to": "end", "messages": [...]}` dict. The LangGraph edge router reads `state.get("jump_to")` — it does not handle `Command` objects from middleware hooks.
  3. Fixed message content extraction for LangChain message objects (`HumanMessage`, `AIMessage`). These use `.type` attribute (`"human"`, `"ai"`), not `.role` (`"user"`, `"assistant"`). The previous code checked `.role` which returned `None` for all LangChain message objects — no content was ever extracted, so scans never fired.

### Changed
- `F5GuardrailMiddleware` now inherits from `langchain.agents.middleware.AgentMiddleware` (with graceful fallback to `object` when `langchain` is not installed). This provides all required base class attributes (`name`, `tools`, `state_schema`, `wrap_tool_call`, etc.).
- Middleware hook signatures updated to match `AgentMiddleware` base class: `before_model(self, state, runtime)` and `after_model(self, state, runtime)` where `state` is the agent state dict directly.
- Removed `langgraph.types.Command` dependency — no longer imported or used.
- Message extraction now supports both plain dicts (`{"role": "user", ...}`) and LangChain message objects (`HumanMessage`, `AIMessage`) via `.type` attribute check.

### Added
- 4 new `TestCanJumpTo` tests verifying `__can_jump_to__` attribute presence on all hook methods.
- Async hooks: `abefore_model` and `aafter_model` with matching `__can_jump_to__` attributes.

## [0.1.0] - 2025-05-20

### Added
- Initial release of `langchain-f5-aiguardrails`
- `F5GuardrailMiddleware` — LangChain agent middleware with `before_model` and `after_model` hooks
- `F5GuardrailClient` — Async-first HTTP client for F5 AI Guardrails scan API
- `GuardrailConfig` — Pydantic configuration with `from_env()` class method
- Pydantic types: `ScanRequest`, `ScanResponse`, `ScanResult`, `ScannerResult`, `ScanDirection`
- Custom exceptions: `F5GuardrailError`, `F5GuardrailAPIError`, `F5GuardrailAuthError`, `F5GuardrailTimeoutError`
- Three enforcement modes: `enforce`, `monitor`, `off`
- Fail-open / fail-closed behavior on API errors
- Violation callback support for monitoring and alerting
- Full test suite with pytest and respx (64 tests)
- Comprehensive documentation
