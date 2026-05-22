"""Session management for F5 AI Guardrails Agentic Fingerprints.

Provides :class:`F5SessionManager` — a lightweight manager for the
``x-cai-metadata-session-id`` header that CalypsoAI uses to correlate
all LLM calls within a single agent workflow run.

Usage::

    from langchain_f5_aiguardrails import F5SessionManager

    # Auto-generate session ID:
    session = F5SessionManager(prefix="k8s-debug")
    print(session.session_id)  # "k8s-debug-a1b2c3d4-..."

    # Provide your own:
    session = F5SessionManager(session_id="my-fixed-id")
"""

from __future__ import annotations

import uuid


# Header name used by CalypsoAI for agentic session tracking.
SESSION_HEADER = "x-cai-metadata-session-id"


class F5SessionManager:
    """Manages a unique session ID for F5 AI Guardrails Agentic Fingerprints.

    CalypsoAI uses the ``x-cai-metadata-session-id`` header to group all LLM
    calls from a single agent workflow into a unified swimlane view.  Each
    session ID must be unique to a single run of the agent.

    Multiple agents in the same workflow should share the **same** session
    manager so that CalypsoAI can build a complete fingerprint of the
    multi-agent interaction.

    Args:
        prefix: Prefix for auto-generated session IDs (default: ``"workflow"``).
            Ignored when *session_id* is provided.
        session_id: Explicit session ID to use.  When ``None``, a new UUID-based
            ID is auto-generated using *prefix*.

    Example::

        session = F5SessionManager(prefix="k8s-debug")

        # Share across multiple agents:
        investigator_llm = ChatF5OpenAI(session_manager=session, ...)
        debugger_llm     = ChatF5OpenAI(session_manager=session, ...)
    """

    def __init__(
        self,
        prefix: str = "workflow",
        *,
        session_id: str | None = None,
    ) -> None:
        if session_id is not None:
            self._session_id = session_id
        else:
            self._session_id = f"{prefix}-{uuid.uuid4()}"

    @property
    def session_id(self) -> str:
        """The current session ID string."""
        return self._session_id

    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers dict containing the session ID header.

        Returns a dict suitable for passing to ``default_headers`` or
        ``extra_headers`` on an OpenAI/Anthropic client::

            {"x-cai-metadata-session-id": "workflow-a1b2c3d4-..."}
        """
        return {SESSION_HEADER: self._session_id}

    def __repr__(self) -> str:
        return f"F5SessionManager(session_id={self._session_id!r})"
