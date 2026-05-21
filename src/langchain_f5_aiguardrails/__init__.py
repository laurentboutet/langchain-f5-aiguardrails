"""LangChain agent middleware for F5 AI Guardrails.

Provides runtime security scanning of LLM prompts and responses
via the F5 AI Guardrails (CalypsoAI) scan API.

Quick start::

    from langchain_f5_aiguardrails import F5GuardrailMiddleware

    middleware = F5GuardrailMiddleware(
        api_key="my-key",
        mode="enforce",
    )
"""

from ._version import __version__
from .client import F5GuardrailClient
from .config import GuardrailConfig
from .exceptions import (
    F5GuardrailAPIError,
    F5GuardrailAuthError,
    F5GuardrailError,
    F5GuardrailTimeoutError,
)
from .middleware import F5GuardrailMiddleware
from .types import ScanDirection, ScanRequest, ScanResponse, ScanResult, ScannerResult

__all__ = [
    "__version__",
    # Core middleware
    "F5GuardrailMiddleware",
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
