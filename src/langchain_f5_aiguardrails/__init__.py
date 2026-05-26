"""LangChain agent middleware for F5 AI Guardrails.

Provides runtime security scanning of LLM prompts and responses
via the F5 AI Guardrails (CalypsoAI) scan API.

Quick start (middleware mode — separate scan API calls)::

    from langchain_f5_aiguardrails import F5GuardrailMiddleware

    middleware = F5GuardrailMiddleware(
        api_key_request="key-for-request-project",
        api_key_response="key-for-response-project",
        mode="enforce",
    )

Quick start (inline proxy mode — LLM traffic routed through F5)::

    from langchain_f5_aiguardrails import ChatF5OpenAI, F5SessionManager

    session = F5SessionManager(prefix="my-workflow")
    llm = ChatF5OpenAI(
        f5_provider="openai-gpt4",
        session_manager=session,
        model="gpt-4o",
    )
"""

from ._version import __version__
from .chat_models import ChatF5OpenAI
from .client import F5GuardrailClient
from .config import GuardrailConfig
from .exceptions import (
    F5GuardrailAPIError,
    F5GuardrailAuthError,
    F5GuardrailError,
    F5GuardrailTimeoutError,
)
from .middleware import F5GuardrailMiddleware
from .session import F5SessionManager
from .types import ScanDirection, ScanRequest, ScanResponse, ScanResult, ScannerResult

__all__ = [
    "__version__",
    # Core middleware (scan API mode)
    "F5GuardrailMiddleware",
    # Inline proxy chat models
    "ChatF5OpenAI",
    "F5SessionManager",
    # HTTP client
    "F5GuardrailClient",
    # Configuration
    "GuardrailConfig",
    # Types
    "ScanDirection",
    "ScanRequest",
    "ScanResponse",
    "ScanResult",
    "ScannerResult",
    # Exceptions
    "F5GuardrailError",
    "F5GuardrailAPIError",
    "F5GuardrailAuthError",
    "F5GuardrailTimeoutError",
]
