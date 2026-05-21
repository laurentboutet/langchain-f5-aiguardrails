# Changelog

All notable changes to `langchain-f5-aiguardrails` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
