"""Configuration management for F5 AI Guardrails middleware.

Provides :class:`GuardrailConfig` — a validated configuration container that
can be instantiated directly or loaded from ``F5_GUARDRAIL_*`` environment
variables via the :meth:`~GuardrailConfig.from_env` class method.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GuardrailConfig(BaseModel):
    """Validated configuration for the F5 AI Guardrails middleware and client.

    Example::

        config = GuardrailConfig(
            api_key="my-key",
            base_url="https://us1.calypsoai.app",
            mode="enforce",
        )

        # Or load from environment variables:
        config = GuardrailConfig.from_env()
    """

    api_key: str = Field(..., description="F5 AI Guardrails API key.")
    base_url: str = Field(
        default="https://us1.calypsoai.app",
        description="Base URL for the F5 AI Guardrails API.",
    )
    project: str | None = Field(default=None, description="Default project ID or friendly ID.")
    mode: Literal["enforce", "monitor", "off"] = Field(
        default="enforce",
        description="Enforcement mode: enforce (block), monitor (log only), off (skip).",
    )
    fail_open: bool = Field(
        default=True,
        description="Allow requests to proceed when the scan API is unreachable.",
    )
    timeout: int = Field(default=30, ge=1, le=300, description="HTTP timeout in seconds.")
    verbose: bool = Field(default=False, description="Request verbose scanner results from the API.")
    blocked_message: str = Field(
        default="This request has been blocked by F5 AI Guardrails security policy.",
        description="Message returned to the user when content is blocked.",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Strip trailing slashes and validate URL format."""
        v = v.rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v

    @classmethod
    def from_env(cls) -> GuardrailConfig:
        """Create a :class:`GuardrailConfig` from ``F5_GUARDRAIL_*`` environment variables.

        Required:
            - ``F5_GUARDRAIL_API_KEY``

        Optional (with defaults):
            - ``F5_GUARDRAIL_BASE_URL`` (default: ``https://us1.calypsoai.app``)
            - ``F5_GUARDRAIL_PROJECT``
            - ``F5_GUARDRAIL_MODE`` (default: ``enforce``)
            - ``F5_GUARDRAIL_FAIL_OPEN`` (default: ``true``)
            - ``F5_GUARDRAIL_TIMEOUT`` (default: ``30``)

        Raises:
            ValueError: If ``F5_GUARDRAIL_API_KEY`` is not set.
        """
        api_key = os.environ.get("F5_GUARDRAIL_API_KEY", "")
        if not api_key:
            raise ValueError(
                "F5_GUARDRAIL_API_KEY environment variable is required. "
                "Set it or pass api_key directly to GuardrailConfig()."
            )

        fail_open_raw = os.environ.get("F5_GUARDRAIL_FAIL_OPEN", "true").lower()
        fail_open = fail_open_raw in ("true", "1", "yes")

        timeout_raw = os.environ.get("F5_GUARDRAIL_TIMEOUT", "30")
        try:
            timeout = int(timeout_raw)
        except ValueError:
            timeout = 30

        return cls(
            api_key=api_key,
            base_url=os.environ.get("F5_GUARDRAIL_BASE_URL", "https://us1.calypsoai.app"),
            project=os.environ.get("F5_GUARDRAIL_PROJECT"),
            mode=os.environ.get("F5_GUARDRAIL_MODE", "enforce"),  # type: ignore[arg-type]
            fail_open=fail_open,
            timeout=timeout,
        )
