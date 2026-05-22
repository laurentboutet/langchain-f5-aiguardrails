"""LangChain chat model wrappers for F5 AI Guardrails inline proxy.

Provides :class:`ChatF5OpenAI` — a drop-in replacement for ``ChatOpenAI``
that routes all LLM traffic through the F5 AI Guardrails proxy and injects
the ``x-cai-metadata-session-id`` header for Agentic Fingerprint tracking.

Usage::

    from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager

    session = F5SessionManager(prefix="my-workflow")

    llm = ChatF5OpenAI(
        f5_provider="openai-gpt4",
        session_manager=session,
        model="gpt-4o",
    )

    response = llm.invoke("Hello!")
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .session import F5SessionManager

logger = logging.getLogger("langchain_f5_aiguardrails.chat_models")

# ---------------------------------------------------------------------------
# Conditional import — langchain-openai is an optional dependency.
# ---------------------------------------------------------------------------

try:
    from langchain_openai import ChatOpenAI as _ChatOpenAIBase
except ImportError:
    _ChatOpenAIBase = None  # type: ignore[assignment,misc]

# Default environment variable names (consistent with existing package).
_ENV_API_KEY = "F5_GUARDRAIL_API_KEY"
_ENV_BASE_URL = "F5_GUARDRAIL_BASE_URL"
_ENV_PROVIDER_OPENAI = "F5_GUARDRAIL_PROVIDER_OPENAI"
_DEFAULT_BASE_URL = "https://us1.calypsoai.app"


def _build_openai_proxy_url(base_url: str, provider: str) -> str:
    """Build the F5 inline proxy URL for OpenAI-compatible calls.

    The F5 AI Guardrails API exposes:
        ``/openai/{provider}/chat/completions``

    LangChain's ``ChatOpenAI`` appends ``/chat/completions`` automatically,
    so we only need to set ``base_url`` to ``{base_url}/openai/{provider}``.

    Args:
        base_url: F5 AI Guardrails base URL (e.g., ``https://us1.calypsoai.app``).
        provider: F5 provider name (e.g., ``openai-gpt4``).

    Returns:
        The proxy URL to use as ``openai_api_base``.
    """
    base_url = base_url.rstrip("/")
    provider = provider.strip("/")
    return f"{base_url}/openai/{provider}"


class ChatF5OpenAI:
    """ChatOpenAI routed through F5 AI Guardrails inline proxy.

    This is a drop-in replacement for ``ChatOpenAI`` that:

    1. Routes all LLM API calls through the F5 AI Guardrails proxy
       (``/openai/{provider}/chat/completions``).
    2. Injects the ``x-cai-metadata-session-id`` header on every request
       so CalypsoAI can build Agentic Fingerprints — a unified swimlane
       view of all agent calls within a workflow.
    3. Uses ``F5_GUARDRAIL_API_KEY`` as the Bearer token for authentication.

    All standard ``ChatOpenAI`` parameters (``model``, ``temperature``,
    ``max_tokens``, etc.) are passed through to the underlying class.

    Args:
        f5_provider: F5 provider name (e.g., ``"openai-gpt4"``).
            Can also be set via ``F5_GUARDRAIL_PROVIDER_OPENAI`` env var.
        f5_base_url: F5 AI Guardrails base URL.
            Can also be set via ``F5_GUARDRAIL_BASE_URL`` env var.
            Defaults to ``https://us1.calypsoai.app``.
        f5_api_key: F5 AI Guardrails API key.
            Can also be set via ``F5_GUARDRAIL_API_KEY`` env var.
        session_manager: Optional :class:`F5SessionManager` for session tracking.
            When provided, the session ID header is injected into every call.
        **kwargs: All other keyword arguments are passed to ``ChatOpenAI``.

    Example::

        from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager

        session = F5SessionManager(prefix="k8s-debug")

        llm = ChatF5OpenAI(
            f5_provider="openai-gpt4",
            session_manager=session,
            model="gpt-4o",
            temperature=0.2,
        )

        # Use with LangChain agents:
        from langchain.agents import create_agent
        agent = create_agent(model=llm, tools=[...])

    Environment variables::

        F5_GUARDRAIL_API_KEY=your-token
        F5_GUARDRAIL_BASE_URL=https://us1.calypsoai.app
        F5_GUARDRAIL_PROVIDER_OPENAI=openai-gpt4

    Raises:
        ImportError: If ``langchain-openai`` is not installed.
        ValueError: If provider name or API key cannot be resolved.
    """

    def __new__(
        cls,
        *,
        f5_provider: str | None = None,
        f5_base_url: str | None = None,
        f5_api_key: str | None = None,
        session_manager: F5SessionManager | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a configured ChatOpenAI instance routed through the F5 proxy.

        We use ``__new__`` so that the returned object **is** a genuine
        ``ChatOpenAI`` instance — it passes ``isinstance`` checks and works
        seamlessly with all LangChain APIs that expect a ``BaseChatModel``.
        """
        if _ChatOpenAIBase is None:
            raise ImportError(
                "langchain-openai is required for ChatF5OpenAI. "
                "Install it with: pip install langchain-openai"
            )

        # --- Resolve F5 parameters from args or env vars ---
        api_key = f5_api_key or os.environ.get(_ENV_API_KEY, "")
        if not api_key:
            raise ValueError(
                f"F5 AI Guardrails API key is required. "
                f"Pass f5_api_key= or set {_ENV_API_KEY} environment variable."
            )

        base_url = f5_base_url or os.environ.get(_ENV_BASE_URL, _DEFAULT_BASE_URL)
        base_url = base_url.rstrip("/")

        provider = f5_provider or os.environ.get(_ENV_PROVIDER_OPENAI, "")
        if not provider:
            raise ValueError(
                f"F5 provider name is required. "
                f"Pass f5_provider= or set {_ENV_PROVIDER_OPENAI} environment variable."
            )

        # --- Build proxy URL ---
        proxy_url = _build_openai_proxy_url(base_url, provider)

        # --- Build default headers ---
        default_headers: dict[str, str] = {}
        if session_manager is not None:
            default_headers.update(session_manager.headers)

        # --- Log configuration ---
        logger.info(
            "ChatF5OpenAI: routing through %s (session=%s)",
            proxy_url,
            session_manager.session_id if session_manager else "none",
        )

        # --- Create the underlying ChatOpenAI ---
        # Override base_url, api_key, and default_headers.
        # All other kwargs (model, temperature, etc.) pass through.
        kwargs["base_url"] = proxy_url
        kwargs["api_key"] = api_key
        if default_headers:
            kwargs["default_headers"] = {
                **default_headers,
                **kwargs.get("default_headers", {}),
            }

        return _ChatOpenAIBase(**kwargs)

    @classmethod
    def from_env(
        cls,
        *,
        session_manager: F5SessionManager | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a ChatF5OpenAI from ``F5_GUARDRAIL_*`` environment variables.

        Required environment variables:
            - ``F5_GUARDRAIL_API_KEY``
            - ``F5_GUARDRAIL_PROVIDER_OPENAI``

        Optional:
            - ``F5_GUARDRAIL_BASE_URL`` (default: ``https://us1.calypsoai.app``)

        Args:
            session_manager: Optional session manager for session tracking.
            **kwargs: Additional arguments passed to ``ChatOpenAI``.

        Returns:
            A configured ``ChatOpenAI`` instance routed through the F5 proxy.
        """
        return cls(session_manager=session_manager, **kwargs)
