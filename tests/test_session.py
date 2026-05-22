"""Tests for F5SessionManager."""

import re
import uuid

import pytest

from langchain_f5_aiguardrails.session import F5SessionManager, SESSION_HEADER


class TestF5SessionManager:
    """Tests for the F5SessionManager class."""

    def test_auto_generate_session_id_with_default_prefix(self) -> None:
        """Session ID is auto-generated with default 'workflow' prefix."""
        session = F5SessionManager()
        assert session.session_id.startswith("workflow-")
        # Verify UUID format after prefix
        uuid_part = session.session_id[len("workflow-") :]
        uuid.UUID(uuid_part)  # Raises if invalid UUID

    def test_auto_generate_session_id_with_custom_prefix(self) -> None:
        """Session ID uses custom prefix when provided."""
        session = F5SessionManager(prefix="k8s-debug")
        assert session.session_id.startswith("k8s-debug-")
        # Verify UUID format after prefix
        uuid_part = session.session_id[len("k8s-debug-") :]
        uuid.UUID(uuid_part)

    def test_explicit_session_id_is_used(self) -> None:
        """Explicit session_id is used when provided."""
        session = F5SessionManager(session_id="my-fixed-id-123")
        assert session.session_id == "my-fixed-id-123"

    def test_explicit_session_id_ignores_prefix(self) -> None:
        """Prefix is ignored when explicit session_id is provided."""
        session = F5SessionManager(prefix="should-be-ignored", session_id="explicit-id")
        assert session.session_id == "explicit-id"
        assert "should-be-ignored" not in session.session_id

    def test_headers_property(self) -> None:
        """headers property returns correct dict with session ID."""
        session = F5SessionManager(session_id="test-session-456")
        headers = session.headers
        assert headers == {"x-cai-metadata-session-id": "test-session-456"}

    def test_headers_uses_correct_header_name(self) -> None:
        """Headers dict uses the SESSION_HEADER constant."""
        session = F5SessionManager()
        headers = session.headers
        assert SESSION_HEADER in headers
        assert headers[SESSION_HEADER] == session.session_id

    def test_session_id_is_immutable(self) -> None:
        """Session ID remains constant for the lifetime of the manager."""
        session = F5SessionManager(prefix="test")
        first_call = session.session_id
        second_call = session.session_id
        assert first_call == second_call

    def test_different_instances_have_different_ids(self) -> None:
        """Each F5SessionManager instance gets a unique session ID."""
        session1 = F5SessionManager()
        session2 = F5SessionManager()
        assert session1.session_id != session2.session_id

    def test_repr(self) -> None:
        """__repr__ includes session ID."""
        session = F5SessionManager(session_id="repr-test")
        assert repr(session) == "F5SessionManager(session_id='repr-test')"

    def test_session_id_format_is_url_safe(self) -> None:
        """Auto-generated session IDs are URL-safe."""
        session = F5SessionManager(prefix="test")
        # Should only contain alphanumeric chars, hyphens, and underscores
        assert re.match(r"^[a-zA-Z0-9_-]+$", session.session_id)
