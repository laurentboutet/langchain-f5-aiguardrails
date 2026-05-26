"""LangChain agent middleware for F5 AI Guardrails security scanning.

Provides :class:`F5GuardrailMiddleware` — an ``AgentMiddleware`` subclass
that scans prompts before model calls and responses after model calls,
blocking or logging unsafe content based on the configured enforcement mode.

The middleware uses **separate API keys** for request and response scanning,
allowing different CalypsoAI projects (with distinct rule sets) for each
direction.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .client import F5GuardrailClient
from .config import GuardrailConfig
from .exceptions import F5GuardrailError
from .types import ScanDirection, ScanRequest, ScanResponse

logger = logging.getLogger("langchain_f5_aiguardrails.middleware")

# ---------------------------------------------------------------------------
# Conditional base class import
# ---------------------------------------------------------------------------
# When ``langchain`` (the full package) is installed, we inherit from its
# ``AgentMiddleware`` base class so that ``create_agent()`` sees the
# expected attributes (``name``, ``tools``, ``wrap_tool_call``, etc.).
#
# When only ``langchain-core`` is present (unit-test / lightweight scenario),
# we fall back to a plain ``object`` base.  The middleware hooks still work
# because ``create_agent`` is never called in that path.
# ---------------------------------------------------------------------------

try:
    from langchain.agents.middleware import AgentMiddleware as _AgentMiddlewareBase
except ImportError:
    _AgentMiddlewareBase = object  # type: ignore[misc,assignment]


class F5GuardrailMiddleware(_AgentMiddlewareBase):  # type: ignore[type-arg]
    """LangChain agent middleware for F5 AI Guardrails.

    Scans prompts (user inputs) before they reach the LLM and responses
    (LLM outputs) before they reach the user. Uses **separate API keys**
    for request and response scanning, allowing different CalypsoAI projects
    (with distinct rule sets) for each direction. Supports three modes:

    - **enforce** — Block unsafe content; agent jumps to end with a blocked message.
    - **monitor** — Log violations and invoke callbacks, but never block.
    - **off** — Skip scanning entirely.

    Example::

        from langchain.agents import create_agent
        from langchain_f5_aiguardrails import F5GuardrailMiddleware

        middleware = F5GuardrailMiddleware(
            api_key_request="key-for-request-project",
            api_key_response="key-for-response-project",
            base_url="https://us1.calypsoai.app",
            mode="enforce",
        )

        agent = create_agent(
            model="openai:gpt-4o",
            tools=[],
            middleware=[middleware],
        )

    The middleware can also be loaded from environment variables::

        middleware = F5GuardrailMiddleware.from_env()

    Environment variables::

        F5_GUARDRAIL_API_KEY_REQUEST=key-for-request-project
        F5_GUARDRAIL_API_KEY_RESPONSE=key-for-response-project
        F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
        F5_GUARDRAIL_MODE=enforce
    """

    # AgentMiddleware protocol attributes
    tools: list = []  # type: ignore[assignment]

    @property
    def name(self) -> str:  # type: ignore[override]
        return "f5_guardrail"

    def __init__(
        self,
        api_key_request: str,
        api_key_response: str,
        base_url: str = "https://us1.calypsoai.app",
        *,
        mode: str = "enforce",
        fail_open: bool = True,
        timeout: int = 30,
        project: str | None = None,
        verbose: bool = False,
        on_violation: Callable[[ScanResponse, ScanDirection], None] | None = None,
        blocked_message: str = "This request has been blocked by F5 AI Guardrails security policy.",
    ) -> None:
        """Initialize the middleware.

        Args:
            api_key_request: F5 AI Guardrails API key for request/prompt scanning.
            api_key_response: F5 AI Guardrails API key for response scanning.
            base_url: Base URL for the F5 scan API.
            mode: Enforcement mode — "enforce", "monitor", or "off".
            fail_open: Allow requests when the scan API is unreachable.
            timeout: HTTP timeout in seconds.
            project: Default project ID for scans.
            verbose: Request verbose scanner results.
            on_violation: Callback invoked on scan violations.
            blocked_message: Message returned when content is blocked.
        """
        self._config = GuardrailConfig(
            api_key_request=api_key_request,
            api_key_response=api_key_response,
            base_url=base_url,
            project=project,
            mode=mode,  # type: ignore[arg-type]
            fail_open=fail_open,
            timeout=timeout,
            verbose=verbose,
            blocked_message=blocked_message,
        )
        # Create separate clients for request and response scanning.
        # Each client uses its own API key, which maps to a distinct
        # CalypsoAI project with its own set of guardrail rules.
        self._request_client = F5GuardrailClient(
            api_key=api_key_request,
            base_url=base_url,
            project=project,
            timeout=timeout,
        )
        self._response_client = F5GuardrailClient(
            api_key=api_key_response,
            base_url=base_url,
            project=project,
            timeout=timeout,
        )
        self._on_violation = on_violation

    # ------------------------------------------------------------------
    # Internal scanning logic
    # ------------------------------------------------------------------

    def _get_client(self, direction: ScanDirection) -> F5GuardrailClient:
        """Return the appropriate client based on scan direction."""
        if direction == ScanDirection.PROMPT:
            return self._request_client
        return self._response_client

    def _scan_content(self, content: str, direction: ScanDirection) -> ScanResponse | None:
        """Scan content synchronously, handling errors per fail_open policy."""
        if self._config.mode == "off":
            return None

        request = ScanRequest(
            input=content,
            project=self._config.project,
            verbose=self._config.verbose,
        )

        try:
            client = self._get_client(direction)
            return client.scan(request)
        except F5GuardrailError as exc:
            logger.warning(
                "Scan API error during %s scan: %s (fail_open=%s)",
                direction.value,
                exc,
                self._config.fail_open,
            )
            if self._config.fail_open:
                return None
            raise

    async def _scan_content_async(self, content: str, direction: ScanDirection) -> ScanResponse | None:
        """Scan content asynchronously, handling errors per fail_open policy."""
        if self._config.mode == "off":
            return None

        request = ScanRequest(
            input=content,
            project=self._config.project,
            verbose=self._config.verbose,
        )

        try:
            client = self._get_client(direction)
            return await client.scan_async(request)
        except F5GuardrailError as exc:
            logger.warning(
                "Scan API error during %s scan: %s (fail_open=%s)",
                direction.value,
                exc,
                self._config.fail_open,
            )
            if self._config.fail_open:
                return None
            raise

    def _handle_scan_result(
        self,
        result: ScanResponse | None,
        direction: ScanDirection,
        state: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Decide whether to block based on scan result and mode.

        Returns:
            None to continue, or a dict with ``jump_to`` and ``messages``
            to terminate the agent.
        """
        if result is None:
            return None

        if result.is_safe:
            logger.debug("Scan %s: content cleared", direction.value)
            return None

        logger.warning(
            "Scan %s violation detected: outcome=%s",
            direction.value,
            result.outcome,
        )

        if self._on_violation is not None:
            try:
                self._on_violation(result, direction)
            except Exception:  # noqa: BLE001
                logger.exception("on_violation callback raised an exception")

        if self._config.mode == "monitor":
            return None

        return self._build_blocked_response(state)

    def _build_blocked_response(self, state: dict[str, Any]) -> dict[str, Any]:
        """Build a state-update dict that terminates the agent with a blocked message.

        The ``jump_to`` key tells the LangGraph edge router to jump to the
        end node, skipping the model call.  The ``messages`` key is the
        state update that replaces the conversation with the blocked message.
        """
        messages = state.get("messages", [])
        blocked_msg = {"role": "assistant", "content": self._config.blocked_message}
        return {
            "jump_to": "end",
            "messages": [*messages, blocked_msg],
        }

    @staticmethod
    def _extract_latest_user_content(state: dict[str, Any]) -> str:
        """Extract the latest user message content from state.

        Handles both plain dicts (``{"role": "user", ...}``) and LangChain
        message objects (``HumanMessage`` with ``.type == "human"``).
        """
        messages = state.get("messages", [])
        for msg in reversed(messages):
            # Plain dicts use "role"; LangChain message objects use "type"
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "type", None)
            if role in ("user", "human"):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                return str(content) if content else ""
        return ""

    @staticmethod
    def _extract_model_response_content(state: dict[str, Any]) -> str:
        """Extract the latest assistant/model response content from state.

        Handles both plain dicts (``{"role": "assistant", ...}``) and LangChain
        message objects (``AIMessage`` with ``.type == "ai"``).
        """
        messages = state.get("messages", [])
        for msg in reversed(messages):
            # Plain dicts use "role"; LangChain message objects use "type"
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                return str(content) if content else ""
        return ""

    # ------------------------------------------------------------------
    # AgentMiddleware hooks
    # ------------------------------------------------------------------
    # Signature: before_model(self, state, runtime) -> dict | None
    #
    # The ``__can_jump_to__`` attribute is inspected by ``create_agent``
    # (via ``_get_can_jump_to``) to wire conditional edges in the graph.
    # Without it, the graph adds only plain edges and ignores jump_to.
    # ------------------------------------------------------------------

    def before_model(self, state: Any, runtime: Any = None) -> dict[str, Any] | None:  # type: ignore[override]
        """Scan the user prompt before the model call (sync).

        Args:
            state: The agent state dict (contains "messages" list).
            runtime: The LangGraph runtime context.

        Returns:
            None to continue normally, or a dict with ``jump_to: "end"``
            plus updated ``messages`` to block and terminate the agent.
        """
        state_dict = state if isinstance(state, dict) else {}

        content = self._extract_latest_user_content(state_dict)
        if not content:
            return None

        result = self._scan_content(content, ScanDirection.PROMPT)
        return self._handle_scan_result(result, ScanDirection.PROMPT, state_dict)

    # Tell create_agent to wire a conditional edge supporting jump_to="end"
    before_model.__can_jump_to__ = ["end"]  # type: ignore[attr-defined]

    async def abefore_model(self, state: Any, runtime: Any = None) -> dict[str, Any] | None:  # type: ignore[override]
        """Scan the user prompt before the model call (async)."""
        state_dict = state if isinstance(state, dict) else {}

        content = self._extract_latest_user_content(state_dict)
        if not content:
            return None

        result = await self._scan_content_async(content, ScanDirection.PROMPT)
        return self._handle_scan_result(result, ScanDirection.PROMPT, state_dict)

    abefore_model.__can_jump_to__ = ["end"]  # type: ignore[attr-defined]

    def after_model(self, state: Any, runtime: Any = None) -> dict[str, Any] | None:  # type: ignore[override]
        """Scan the model response after the model call (sync).

        Args:
            state: The agent state dict (contains "messages" list with model response).
            runtime: The LangGraph runtime context.

        Returns:
            None to continue normally, or a dict with ``jump_to: "end"``
            plus updated ``messages`` to block the response.
        """
        state_dict = state if isinstance(state, dict) else {}

        content = self._extract_model_response_content(state_dict)
        if not content:
            return None

        result = self._scan_content(content, ScanDirection.RESPONSE)
        return self._handle_scan_result(result, ScanDirection.RESPONSE, state_dict)

    after_model.__can_jump_to__ = ["end"]  # type: ignore[attr-defined]

    async def aafter_model(self, state: Any, runtime: Any = None) -> dict[str, Any] | None:  # type: ignore[override]
        """Scan the model response after the model call (async)."""
        state_dict = state if isinstance(state, dict) else {}

        content = self._extract_model_response_content(state_dict)
        if not content:
            return None

        result = await self._scan_content_async(content, ScanDirection.RESPONSE)
        return self._handle_scan_result(result, ScanDirection.RESPONSE, state_dict)

    aafter_model.__can_jump_to__ = ["end"]  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP clients and release connections."""
        self._request_client.close()
        self._response_client.close()

    async def close_async(self) -> None:
        """Close the underlying async HTTP clients and release connections."""
        await self._request_client.close_async()
        await self._response_client.close_async()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        *,
        on_violation: Callable[[ScanResponse, ScanDirection], None] | None = None,
    ) -> F5GuardrailMiddleware:
        """Create middleware from ``F5_GUARDRAIL_*`` environment variables.

        Required:
            - ``F5_GUARDRAIL_API_KEY_REQUEST``
            - ``F5_GUARDRAIL_API_KEY_RESPONSE``
        """
        config = GuardrailConfig.from_env()
        return cls(
            api_key_request=config.api_key_request,
            api_key_response=config.api_key_response,
            base_url=config.base_url,
            mode=config.mode,
            fail_open=config.fail_open,
            timeout=config.timeout,
            project=config.project,
            verbose=config.verbose,
            on_violation=on_violation,
            blocked_message=config.blocked_message,
        )
