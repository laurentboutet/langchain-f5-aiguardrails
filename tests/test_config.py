"""Tests for GuardrailConfig configuration."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from langchain_f5_aiguardrails import GuardrailConfig


class TestGuardrailConfig:
    def test_defaults(self):
        config = GuardrailConfig(api_key_request="req-key", api_key_response="resp-key")
        assert config.api_key_request == "req-key"
        assert config.api_key_response == "resp-key"
        assert config.base_url == "https://us1.calypsoai.app"
        assert config.project is None
        assert config.mode == "enforce"
        assert config.fail_open is True
        assert config.timeout == 30
        assert config.verbose is False
        assert "blocked" in config.blocked_message.lower()

    def test_custom_values(self):
        config = GuardrailConfig(
            api_key_request="req-key",
            api_key_response="resp-key",
            base_url="https://eu1.calypsoai.app",
            project="my-project",
            mode="monitor",
            fail_open=False,
            timeout=60,
            verbose=True,
            blocked_message="Custom blocked message",
        )
        assert config.base_url == "https://eu1.calypsoai.app"
        assert config.project == "my-project"
        assert config.mode == "monitor"
        assert config.fail_open is False
        assert config.timeout == 60
        assert config.verbose is True
        assert config.blocked_message == "Custom blocked message"

    def test_separate_api_keys(self):
        """Request and response API keys are stored separately."""
        config = GuardrailConfig(
            api_key_request="request-project-key",
            api_key_response="response-project-key",
        )
        assert config.api_key_request == "request-project-key"
        assert config.api_key_response == "response-project-key"
        assert config.api_key_request != config.api_key_response

    def test_same_api_key_for_both(self):
        """User can set the same key for both directions (single project)."""
        config = GuardrailConfig(
            api_key_request="same-key",
            api_key_response="same-key",
        )
        assert config.api_key_request == config.api_key_response

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            GuardrailConfig(api_key_request="k1", api_key_response="k2", mode="invalid")

    def test_base_url_trailing_slash_stripped(self):
        config = GuardrailConfig(
            api_key_request="k1", api_key_response="k2",
            base_url="https://us1.calypsoai.app///",
        )
        assert config.base_url == "https://us1.calypsoai.app"

    def test_base_url_invalid_protocol(self):
        with pytest.raises(ValidationError, match="http"):
            GuardrailConfig(
                api_key_request="k1", api_key_response="k2",
                base_url="ftp://example.com",
            )

    def test_timeout_range(self):
        with pytest.raises(ValidationError):
            GuardrailConfig(api_key_request="k1", api_key_response="k2", timeout=0)
        with pytest.raises(ValidationError):
            GuardrailConfig(api_key_request="k1", api_key_response="k2", timeout=301)


class TestGuardrailConfigFromEnv:
    def test_from_env_all_set(self, monkeypatch):
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_REQUEST", "env-req-key")
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_RESPONSE", "env-resp-key")
        monkeypatch.setenv("F5_GUARDRAIL_BASE_URL", "https://eu1.calypsoai.app")
        monkeypatch.setenv("F5_GUARDRAIL_PROJECT", "env-project")
        monkeypatch.setenv("F5_GUARDRAIL_MODE", "monitor")
        monkeypatch.setenv("F5_GUARDRAIL_FAIL_OPEN", "false")
        monkeypatch.setenv("F5_GUARDRAIL_TIMEOUT", "60")

        config = GuardrailConfig.from_env()

        assert config.api_key_request == "env-req-key"
        assert config.api_key_response == "env-resp-key"
        assert config.base_url == "https://eu1.calypsoai.app"
        assert config.project == "env-project"
        assert config.mode == "monitor"
        assert config.fail_open is False
        assert config.timeout == 60

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_REQUEST", "env-req-key")
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_RESPONSE", "env-resp-key")
        # Ensure others are not set
        monkeypatch.delenv("F5_GUARDRAIL_BASE_URL", raising=False)
        monkeypatch.delenv("F5_GUARDRAIL_PROJECT", raising=False)
        monkeypatch.delenv("F5_GUARDRAIL_MODE", raising=False)
        monkeypatch.delenv("F5_GUARDRAIL_FAIL_OPEN", raising=False)
        monkeypatch.delenv("F5_GUARDRAIL_TIMEOUT", raising=False)

        config = GuardrailConfig.from_env()

        assert config.api_key_request == "env-req-key"
        assert config.api_key_response == "env-resp-key"
        assert config.base_url == "https://us1.calypsoai.app"
        assert config.mode == "enforce"
        assert config.fail_open is True
        assert config.timeout == 30

    def test_from_env_missing_request_api_key(self, monkeypatch):
        monkeypatch.delenv("F5_GUARDRAIL_API_KEY_REQUEST", raising=False)
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_RESPONSE", "resp-key")

        with pytest.raises(ValueError, match="F5_GUARDRAIL_API_KEY_REQUEST"):
            GuardrailConfig.from_env()

    def test_from_env_missing_response_api_key(self, monkeypatch):
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_REQUEST", "req-key")
        monkeypatch.delenv("F5_GUARDRAIL_API_KEY_RESPONSE", raising=False)

        with pytest.raises(ValueError, match="F5_GUARDRAIL_API_KEY_RESPONSE"):
            GuardrailConfig.from_env()

    def test_from_env_missing_both_api_keys(self, monkeypatch):
        monkeypatch.delenv("F5_GUARDRAIL_API_KEY_REQUEST", raising=False)
        monkeypatch.delenv("F5_GUARDRAIL_API_KEY_RESPONSE", raising=False)

        with pytest.raises(ValueError, match="F5_GUARDRAIL_API_KEY_REQUEST"):
            GuardrailConfig.from_env()

    def test_from_env_fail_open_variants(self, monkeypatch):
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_REQUEST", "req-key")
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_RESPONSE", "resp-key")

        for truthy in ("true", "True", "TRUE", "1", "yes"):
            monkeypatch.setenv("F5_GUARDRAIL_FAIL_OPEN", truthy)
            assert GuardrailConfig.from_env().fail_open is True

        for falsy in ("false", "False", "0", "no"):
            monkeypatch.setenv("F5_GUARDRAIL_FAIL_OPEN", falsy)
            assert GuardrailConfig.from_env().fail_open is False

    def test_from_env_invalid_timeout(self, monkeypatch):
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_REQUEST", "req-key")
        monkeypatch.setenv("F5_GUARDRAIL_API_KEY_RESPONSE", "resp-key")
        monkeypatch.setenv("F5_GUARDRAIL_TIMEOUT", "not-a-number")

        config = GuardrailConfig.from_env()
        assert config.timeout == 30  # fallback to default
