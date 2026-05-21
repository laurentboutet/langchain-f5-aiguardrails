"""Custom exception hierarchy for F5 AI Guardrails middleware.

All exceptions inherit from :class:`F5GuardrailError` so callers can catch
a single base class when they want to handle any guardrail-related failure.
"""

from __future__ import annotations


class F5GuardrailError(Exception):
    """Base exception for all F5 AI Guardrails errors."""


class F5GuardrailAPIError(F5GuardrailError):
    """Raised when the F5 scan API returns an unexpected HTTP status.

    Attributes:
        status_code: The HTTP status code returned by the API.
        body: The raw response body, if available.
    """

    def __init__(self, message: str, *, status_code: int, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class F5GuardrailAuthError(F5GuardrailError):
    """Raised on HTTP 401 or 403 — the API key is invalid or lacks permissions."""

    def __init__(self, message: str = "Authentication failed: check your F5_GUARDRAIL_API_KEY.") -> None:
        super().__init__(message)


class F5GuardrailTimeoutError(F5GuardrailError):
    """Raised when a scan request exceeds the configured timeout."""

    def __init__(self, message: str = "Scan request timed out.", *, timeout: int | float = 0) -> None:
        super().__init__(message)
        self.timeout = timeout
