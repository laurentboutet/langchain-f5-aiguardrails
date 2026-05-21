"""Shared fixtures for F5 AI Guardrails middleware tests."""

from __future__ import annotations

import pytest

from langchain_f5_aiguardrails import F5GuardrailClient, F5GuardrailMiddleware

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_URL = "https://us1.calypsoai.app"
MOCK_API_KEY = "test-api-key-12345"


# ---------------------------------------------------------------------------
# JSON response fixtures — mirror the F5 AI Guardrails API schema
# ---------------------------------------------------------------------------

@pytest.fixture()
def cleared_response_json() -> dict:
    """API response for content that passed all scanners."""
    return {
        "id": "scan-001",
        "result": {
            "outcome": "cleared",
            "scannerResults": [],
        },
        "redactedInput": "",
    }


@pytest.fixture()
def blocked_response_json() -> dict:
    """API response for content blocked by a scanner."""
    return {
        "id": "scan-002",
        "result": {
            "outcome": "blocked",
            "scannerResults": [
                {
                    "scannerId": "scanner-prompt-injection",
                    "outcome": "blocked",
                    "scanDirection": "request",
                    "startedDate": "2025-01-01T00:00:00Z",
                    "completedDate": "2025-01-01T00:00:01Z",
                    "data": {"reason": "Prompt injection detected"},
                    "customConfig": False,
                }
            ],
        },
        "redactedInput": "",
    }


@pytest.fixture()
def flagged_response_json() -> dict:
    """API response for content flagged by a scanner."""
    return {
        "id": "scan-003",
        "result": {
            "outcome": "flagged",
            "scannerResults": [
                {
                    "scannerId": "scanner-toxicity",
                    "outcome": "flagged",
                    "scanDirection": "request",
                    "startedDate": "2025-01-01T00:00:00Z",
                    "completedDate": "2025-01-01T00:00:01Z",
                    "data": {"score": 0.85},
                    "customConfig": False,
                }
            ],
        },
        "redactedInput": "",
    }


@pytest.fixture()
def redacted_response_json() -> dict:
    """API response for content that was redacted (PII masked)."""
    return {
        "id": "scan-004",
        "result": {
            "outcome": "redacted",
            "scannerResults": [
                {
                    "scannerId": "scanner-pii",
                    "outcome": "redacted",
                    "scanDirection": "request",
                    "data": {"redacted_fields": ["email", "phone"]},
                    "customConfig": False,
                }
            ],
        },
        "redactedInput": "Hello, my email is [REDACTED] and phone is [REDACTED].",
    }


# ---------------------------------------------------------------------------
# Client and middleware fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def guardrail_client() -> F5GuardrailClient:
    """Pre-configured F5GuardrailClient for testing."""
    return F5GuardrailClient(
        api_key=MOCK_API_KEY,
        base_url=API_BASE_URL,
        timeout=5,
    )


@pytest.fixture()
def middleware_enforce() -> F5GuardrailMiddleware:
    """Middleware in enforce mode."""
    return F5GuardrailMiddleware(
        api_key=MOCK_API_KEY,
        base_url=API_BASE_URL,
        mode="enforce",
        timeout=5,
    )


@pytest.fixture()
def middleware_monitor() -> F5GuardrailMiddleware:
    """Middleware in monitor mode."""
    return F5GuardrailMiddleware(
        api_key=MOCK_API_KEY,
        base_url=API_BASE_URL,
        mode="monitor",
        timeout=5,
    )
