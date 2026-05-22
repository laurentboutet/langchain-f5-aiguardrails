"""Tests for ChatF5OpenAI wrapper."""

import os
from unittest.mock import MagicMock, patch

import pytest

from langchain_f5_aiguardrails.chat_models import (
    ChatF5OpenAI,
    _build_openai_proxy_url,
    _ENV_API_KEY,
    _ENV_BASE_URL,
    _ENV_PROVIDER_OPENAI,
)
from langchain_f5_aiguardrails.session import F5SessionManager


class TestBuildOpenAIProxyUrl:
    """Tests for the _build_openai_proxy_url helper function."""

    def test_basic_url_building(self) -> None:
        """Builds correct proxy URL from base URL and provider."""
        url = _build_openai_proxy_url("https://us1.calypsoai.app", "openai-gpt4")
        assert url == "https://us1.calypsoai.app/openai/openai-gpt4"

    def test_strips_trailing_slash_from_base_url(self) -> None:
        """Trailing slashes are removed from base URL."""
        url = _build_openai_proxy_url("https://us1.calypsoai.app/", "my-provider")
        assert url == "https://us1.calypsoai.app/openai/my-provider"

    def test_strips_slashes_from_provider(self) -> None:
        """Leading/trailing slashes are removed from provider."""
        url = _build_openai_proxy_url("https://api.example.com", "/provider-name/")
        assert url == "https://api.example.com/openai/provider-name"

    def test_multiple_trailing_slashes(self) -> None:
        """Multiple trailing slashes are stripped."""
        url = _build_openai_proxy_url("https://api.example.com///", "prov")
        # rstrip only removes from the end
        assert "/openai/prov" in url


class TestChatF5OpenAI:
    """Tests for the ChatF5OpenAI class."""

    @pytest.fixture
    def mock_chat_openai(self) -> MagicMock:
        """Create a mock ChatOpenAI class."""
        return MagicMock()

    @pytest.fixture
    def env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up environment variables for tests."""
        monkeypatch.setenv(_ENV_API_KEY, "test-api-key-12345")
        monkeypatch.setenv(_ENV_BASE_URL, "https://test.calypsoai.app")
        monkeypatch.setenv(_ENV_PROVIDER_OPENAI, "test-openai-provider")

    def test_raises_import_error_when_langchain_openai_not_installed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raises ImportError when langchain-openai is not installed."""
        # Temporarily patch the module-level import check
        import langchain_f5_aiguardrails.chat_models as chat_module

        original = chat_module._ChatOpenAIBase
        chat_module._ChatOpenAIBase = None

        try:
            with pytest.raises(ImportError, match="langchain-openai is required"):
                ChatF5OpenAI(
                    f5_provider="test",
                    f5_api_key="key",
                )
        finally:
            chat_module._ChatOpenAIBase = original

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase", new_callable=lambda: MagicMock)
    def test_raises_value_error_when_api_key_missing(
        self,
        mock_base: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raises ValueError when API key is not provided."""
        monkeypatch.delenv(_ENV_API_KEY, raising=False)

        with pytest.raises(ValueError, match="API key is required"):
            ChatF5OpenAI(f5_provider="test-provider")

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase", new_callable=lambda: MagicMock)
    def test_raises_value_error_when_provider_missing(
        self,
        mock_base: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raises ValueError when provider is not provided."""
        monkeypatch.setenv(_ENV_API_KEY, "test-key")
        monkeypatch.delenv(_ENV_PROVIDER_OPENAI, raising=False)

        with pytest.raises(ValueError, match="provider name is required"):
            ChatF5OpenAI(f5_api_key="test-key")

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_creates_chat_openai_with_correct_base_url(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """ChatOpenAI is created with correct proxy base_url."""
        ChatF5OpenAI(model="gpt-4o")

        mock_base.assert_called_once()
        call_kwargs = mock_base.call_args.kwargs
        assert call_kwargs["base_url"] == "https://test.calypsoai.app/openai/test-openai-provider"

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_creates_chat_openai_with_api_key(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """ChatOpenAI is created with correct API key."""
        ChatF5OpenAI(model="gpt-4o")

        call_kwargs = mock_base.call_args.kwargs
        assert call_kwargs["api_key"] == "test-api-key-12345"

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_injects_session_headers_when_session_manager_provided(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """Session ID header is injected when session_manager is provided."""
        session = F5SessionManager(session_id="test-session-xyz")
        ChatF5OpenAI(session_manager=session, model="gpt-4o")

        call_kwargs = mock_base.call_args.kwargs
        assert "default_headers" in call_kwargs
        assert call_kwargs["default_headers"]["x-cai-metadata-session-id"] == "test-session-xyz"

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_no_session_header_when_session_manager_not_provided(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """No session header when session_manager is None."""
        ChatF5OpenAI(model="gpt-4o")

        call_kwargs = mock_base.call_args.kwargs
        # Either no default_headers key, or it doesn't have session header
        headers = call_kwargs.get("default_headers", {})
        assert "x-cai-metadata-session-id" not in headers

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_passes_through_model_kwargs(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """Additional kwargs (model, temperature, etc.) are passed through."""
        ChatF5OpenAI(
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=1000,
        )

        call_kwargs = mock_base.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 1000

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_explicit_params_override_env_vars(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """Explicit parameters override environment variables."""
        ChatF5OpenAI(
            f5_provider="explicit-provider",
            f5_base_url="https://explicit.example.com",
            f5_api_key="explicit-key",
            model="gpt-4o",
        )

        call_kwargs = mock_base.call_args.kwargs
        assert call_kwargs["base_url"] == "https://explicit.example.com/openai/explicit-provider"
        assert call_kwargs["api_key"] == "explicit-key"

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_merges_user_provided_default_headers(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """User-provided default_headers are merged with session headers."""
        session = F5SessionManager(session_id="session-123")
        ChatF5OpenAI(
            session_manager=session,
            default_headers={"X-Custom-Header": "custom-value"},
            model="gpt-4o",
        )

        call_kwargs = mock_base.call_args.kwargs
        headers = call_kwargs["default_headers"]
        # Both session header and custom header should be present
        assert headers["x-cai-metadata-session-id"] == "session-123"
        assert headers["X-Custom-Header"] == "custom-value"

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_from_env_factory_method(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """from_env() creates instance using environment variables."""
        session = F5SessionManager(session_id="env-session")
        ChatF5OpenAI.from_env(session_manager=session, model="gpt-4o")

        call_kwargs = mock_base.call_args.kwargs
        assert call_kwargs["base_url"] == "https://test.calypsoai.app/openai/test-openai-provider"
        assert call_kwargs["api_key"] == "test-api-key-12345"
        assert call_kwargs["default_headers"]["x-cai-metadata-session-id"] == "env-session"

    @patch("langchain_f5_aiguardrails.chat_models._ChatOpenAIBase")
    def test_returns_chat_openai_instance(
        self,
        mock_base: MagicMock,
        env_vars: None,
    ) -> None:
        """ChatF5OpenAI returns the ChatOpenAI instance (not a wrapper)."""
        mock_instance = MagicMock()
        mock_base.return_value = mock_instance

        result = ChatF5OpenAI(model="gpt-4o")

        assert result is mock_instance
